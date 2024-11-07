const API_URL = 'http://127.0.0.1:8000';

chrome.runtime.onInstalled.addListener(() => {
    // Ensure UUID creation on first installation
    chrome.storage.local.get("userUUID", (data) => {
        if (!data.userUUID) {
            const uuid = crypto.randomUUID();
            chrome.storage.local.set({ userUUID: uuid });
        }
    });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'startClientCrawl') {
        const crawlConfig = message.crawlConfig;
        startClientCrawl(crawlConfig);
        sendResponse({ message: 'Client-side crawling started' });
    }
    return true; // Indicates that the response is sent asynchronously
});

async function startClientCrawl(crawlConfig) {
    // Create crawl session in the backend
    const response = await fetch(`${API_URL}/create-crawl-session/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(crawlConfig)
    });

    if (response.ok) {
        const result = await response.json();
        
        // Check for the custom header 'user-uuid-update'
        const updatedUUID = response.headers.get("user-uuid-update");
        if (updatedUUID) {
            // Update the userUUID in Chrome storage
            chrome.storage.local.set({ userUUID: updatedUUID });
        }
        const crawlId = result.crawl_id;

        // Ensure the offscreen document is created
        await ensureOffscreenDocument();

        // Start crawling process
        crawlConfig.crawl_id = crawlId;
        crawlConfig.crawl_session_id = result.crawl_session_id;
        clientCrawler(crawlConfig);
    } else {
        console.error('Failed to create crawl session:', response.statusText);
    }
}

async function ensureOffscreenDocument() {
    const offscreenUrl = 'offscreen.html';

    const existing = await chrome.offscreen.hasDocument();
    if (existing) {
        return;
    }

    await chrome.offscreen.createDocument({
        url: offscreenUrl,
        reasons: [chrome.offscreen.Reason.DOM_PARSER],
        justification: 'Parse HTML content to extract links'
    });
}

async function clientCrawler(crawlConfig) {
    const {
        crawl_id,
        start_urls,
        max_links,
        follow_external,
        depth_limit,
        delay,
        only_child_pages,
        crawl_session_id,
        concurrent_requests // Maximum concurrent requests
    } = crawlConfig;

    let queue = start_urls.map(url => ({ url, depth: 0 }));
    let visited = new Set();
    let linkCount = 0;

    const baseUrl = new URL(start_urls[0]);
    const baseDomain = baseUrl.hostname;
    let basePath = baseUrl.pathname;

    if (only_child_pages) {
        let pathSegments = basePath.split('/').filter(segment => segment); // Remove empty segments

        // Handle the case where the last segment is a file, e.g., 'en.html' -> 'en'
        if (pathSegments.length > 0 && pathSegments[pathSegments.length - 1].includes('.')) {
            pathSegments[pathSegments.length - 1] = pathSegments[pathSegments.length - 1].split('.')[0];
        }
        // Join the path segments back, forming the desired top-level path
        basePath =  `/${pathSegments.join('/')}`;
        console.log("basePath => ", basePath);
    }     

    async function processQueue() {
        while (queue.length > 0 && linkCount < max_links) {
            const currentBatch = queue.splice(0, concurrent_requests);
    
            await Promise.all(
                currentBatch.map(async ({ url, depth }) => {
                    // Centralized check for linkCount
                    if (linkCount >= max_links) return;
    
                    if (visited.has(url) || depth > depth_limit) {
                        return; // Skip if already visited or depth limit exceeded
                    }
    
                    visited.add(url);
    
                    try {
                        const response = await fetch(url, { credentials: 'omit' });
                        const contentType = response.headers.get('Content-Type');
                        if (!contentType || !contentType.includes('text/html')) return;
    
                        const html = await response.text();
                        const parsedData = await parseHTMLInOffscreen(html, url);
                        const { title, text, links, faviconUrl } = parsedData;
    
                        // Increment the counter and check after incrementing
                        linkCount++;
                        if (linkCount > max_links) return;
    
                        const websiteData = {
                            website_url: url,
                            title,
                            text,
                            html,
                            status: true,
                            crawl_session_id,
                            favicon_url: faviconUrl
                        };
    
                        await fetch(`${API_URL}/store-website-data/`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                website_data: websiteData,
                                crawl_session_update: { crawl_id, link_count: linkCount }
                            })
                        });
    
                        if (depth < depth_limit && linkCount < max_links) {
                            for (const link of links) {
                                if (linkCount >= max_links) break; // Stop processing new links
    
                                const linkUrl = new URL(link);
    
                                if (!follow_external && linkUrl.hostname !== baseDomain) continue;
    
                                if (only_child_pages) {
                                    let linkPath = linkUrl.pathname;
                                    linkPath = linkPath.includes('.') ? linkPath.substring(0, linkPath.lastIndexOf('/') + 1) : linkPath;
                                    if (!linkPath.endsWith('/')) linkPath += '/';
                                    if (!linkPath.startsWith(basePath)) continue;
                                }
    
                                if (!visited.has(link)) {
                                    queue.push({ url: link, depth: depth + 1 });
                                }
                            }
                        }
    
                        if (delay > 0) {
                            await new Promise(resolve => setTimeout(resolve, delay * 1000));
                        }
    
                    } catch (error) {
                        console.error(`Error fetching ${url}: ${error}`);
                    }
                })
            );
    
            // Ensure no further queue processing if limit is reached after batch
            if (linkCount >= max_links) break;
        }
    }

    await processQueue();

    // Update crawl session status to 'completed' in backend
    await fetch(`${API_URL}/store-website-data/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            crawl_session_update: { crawl_id, status: "completed" }
        })
    });

    await chrome.offscreen.closeDocument();
    console.log('Client-side crawling completed');
}

async function parseHTMLInOffscreen(html, url) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ action: 'parseHTML', html, url }, (response) => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                resolve(response);
            }
        });
    });
}