const API_URL = 'http://127.0.0.1:8000';
const crawlingSessions = {}; // To keep track of active crawling sessions

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
    } else if (message.action === 'pauseCrawl') {
        const crawler = crawlingSessions[message.crawlId];
        if (crawler) {
            crawler.pause();
            sendResponse({ message: 'Crawl paused' });
        } else {
            sendResponse({ message: 'Crawl not found' });
        }
    } else if (message.action === 'resumeCrawl') {
        let crawler = crawlingSessions[message.crawlId];
        if (crawler) {
            crawler.resume();
            sendResponse({ message: 'Crawl resumed' });
        } else {
            // Try to load state from storage
            chrome.storage.local.get('crawlState_' + message.crawlId, async (data) => {
                const state = data['crawlState_' + message.crawlId];
                if (state) {
                    // Recreate crawler instance
                    crawler = new Crawler(state.crawlConfig);
                    crawler.queue = state.queue;
                    crawler.visited = new Set(state.visited);
                    crawler.linkCount = state.linkCount;
                    // Start the crawler
                    crawlingSessions[message.crawlId] = crawler;
                    await crawler.resume();
                    sendResponse({ message: 'Crawl resumed from saved state' });
                } else {
                    sendResponse({ message: 'No saved state found for crawl' });
                }
            });
            return true; // Indicates asynchronous response
        }
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
        const crawler = new Crawler(crawlConfig);
        crawlingSessions[crawlId] = crawler;
        crawler.start();
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

class Crawler {
    constructor(crawlConfig) {
        const {
            crawl_id,
            crawl_session_id,
            start_urls,
            max_links,
            follow_external,
            depth_limit,
            delay,
            only_child_pages,
            concurrent_requests // Maximum concurrent requests
        } = crawlConfig;

        this.crawl_id = crawl_id;
        this.crawl_session_id = crawl_session_id;
        this.queue = start_urls.map(url => ({ url, depth: 0 }));
        this.visited = new Set();
        this.linkCount = 0;
        this.isPaused = false;
        this.processing = false;
        this.status = 'running';
        this.abortControllers = [];
        this.crawlConfig = crawlConfig;

        this.start_urls = start_urls;
        this.max_links = max_links;
        this.follow_external = follow_external;
        this.depth_limit = depth_limit;
        this.delay = delay;
        this.only_child_pages = only_child_pages;
        this.concurrent_requests = concurrent_requests;

        this.baseUrl = new URL(start_urls[0]);
        this.baseDomain = this.baseUrl.hostname;
        this.basePath = this.baseUrl.pathname;

        if (only_child_pages) {
            let pathSegments = this.basePath.split('/').filter(segment => segment); // Remove empty segments

            // Handle the case where the last segment is a file, e.g., 'en.html' -> 'en'
            if (pathSegments.length > 0 && pathSegments[pathSegments.length - 1].includes('.')) {
                pathSegments[pathSegments.length - 1] = pathSegments[pathSegments.length - 1].split('.')[0];
            }
            // Join the path segments back, forming the desired top-level path
            this.basePath =  `/${pathSegments.join('/')}`;
            console.log("basePath => ", this.basePath);
        }
    }

    async start() {
        this.processing = true;
        await this.processQueue();
        this.processing = false;
        delete crawlingSessions[this.crawl_id];
    }

    normalizeUrl(url) {
        // Normalize URL by removing fragment (#...) and trailing slash if present
        const parsedUrl = new URL(url);
        parsedUrl.hash = '';  // Remove fragment
        parsedUrl.pathname = parsedUrl.pathname.replace(/\/$/, '');  // Remove trailing slash
        return parsedUrl.toString();
    }

    async processQueue() {
        while (this.queue.length > 0 && this.linkCount < this.max_links) {
            if (this.isPaused) {
                await this.waitUntilResumed();
            }

            const currentBatch = this.queue.splice(0, this.concurrent_requests);
    
            await Promise.all(
                currentBatch.map(async ({ url, depth }) => {
                    if (this.isPaused) return;

                    // Centralized check for linkCount
                    if (this.linkCount >= this.max_links) return;

                    const normalizedUrl = this.normalizeUrl(url);
    
                    if (this.visited.has(normalizedUrl) || depth > this.depth_limit) {
                        return; // Skip if already visited or depth limit exceeded
                    }
    
                    this.visited.add(normalizedUrl);

                    const controller = new AbortController();
                    this.abortControllers.push(controller);
    
                    try {
                        const response = await fetch(url, { credentials: 'omit', signal: controller.signal });
                        const contentType = response.headers.get('Content-Type');
                        if (!contentType || !contentType.includes('text/html')) return;
    
                        const html = await response.text();
                        const parsedData = await parseHTMLInOffscreen(html, url);
                        const { title, text, links, faviconUrl } = parsedData;
    
                        // Increment the counter and check after incrementing
                        this.linkCount++;
                        if (this.linkCount > this.max_links) return;
    
                        const websiteData = {
                            website_url: url,
                            title,
                            text,
                            html,
                            status: true,
                            crawl_session_id: this.crawl_session_id,
                            favicon_url: faviconUrl
                        };
    
                        await fetch(`${API_URL}/store-website-data/`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                website_data: websiteData,
                                crawl_session_update: { crawl_id: this.crawl_id, link_count: this.linkCount }
                            })
                        });
    
                        if (depth < this.depth_limit && this.linkCount < this.max_links) {
                            for (const link of links) {
                                if (this.linkCount >= this.max_links) break; // Stop processing new links
    
                                const linkUrl = new URL(link);
    
                                if (!this.follow_external && linkUrl.hostname !== this.baseDomain) continue;
    
                                if (this.only_child_pages) {
                                    let linkPath = linkUrl.pathname;
                                    linkPath = linkPath.includes('.') ? linkPath.substring(0, linkPath.lastIndexOf('/') + 1) : linkPath;
                                    if (!linkPath.endsWith('/')) linkPath += '/';
                                    if (!linkPath.startsWith(this.basePath)) continue;
                                }
    
                                const normalizedLink = this.normalizeUrl(link);
                                if (!this.visited.has(normalizedLink)) {
                                    this.queue.push({ url: normalizedLink, depth: depth + 1 });
                                }
                            }
                        }
    
                        if (this.delay > 0) {
                            await new Promise(resolve => setTimeout(resolve, this.delay * 1000));
                        }
    
                    } catch (error) {
                        if (error.name === 'AbortError') {
                            console.log(`Fetch aborted for ${url}`);
                        } else {
                            console.error(`Error fetching ${url}: ${error}`);
                        }
                    } finally {
                        this.abortControllers = this.abortControllers.filter(c => c !== controller);
                    }
                })
            );
    
            // Ensure no further queue processing if limit is reached after batch
            if (this.linkCount >= this.max_links) break;

            if (this.isPaused) {
                await this.waitUntilResumed();
            }
        }

        // Update crawl session status to 'completed' in backend
        await fetch(`${API_URL}/store-website-data/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                crawl_session_update: { crawl_id: this.crawl_id, status: "completed" }
            })
        });
    
        await chrome.offscreen.closeDocument();
        console.log('Client-side crawling completed');
    }

    pause() {
        this.isPaused = true;
        this.status = 'paused';

        // Abort ongoing fetch requests
        this.abortControllers.forEach(controller => controller.abort());
        this.abortControllers = [];

        // Save state to storage
        const state = {
            crawl_id: this.crawl_id,
            crawl_session_id: this.crawl_session_id,
            queue: this.queue,
            visited: Array.from(this.visited),
            linkCount: this.linkCount,
            // ... other properties
            crawlConfig: this.crawlConfig
        };
        chrome.storage.local.set({ ['crawlState_' + this.crawl_id]: state });

        // Update crawl session status in backend
        fetch(`${API_URL}/store-website-data/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                crawl_session_update: { crawl_id: this.crawl_id, status: "paused" }
            })
        });
    }

    async resume() {
        this.isPaused = false;
        this.status = 'running';

        // Update crawl session status in backend
        await fetch(`${API_URL}/store-website-data/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                crawl_session_update: { crawl_id: this.crawl_id, status: "running" }
            })
        });

        if (!this.processing) {
            this.start();
        }
    }

    async waitUntilResumed() {
        return new Promise(resolve => {
            const interval = setInterval(() => {
                if (!this.isPaused) {
                    clearInterval(interval);
                    resolve();
                }
            }, 100);
        });
    }
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