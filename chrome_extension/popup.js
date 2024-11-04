const API_URL = 'http://127.0.0.1:8000';

document.addEventListener("DOMContentLoaded", async function () {
    async function getUserUUID() {
        return new Promise((resolve) => {
            chrome.storage.local.get("userUUID", async (data) => {
                if (data.userUUID) {
                    resolve(data.userUUID);
                } else {
                    const response = await fetch(`${API_URL}/create-user/`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        const uuid = result.uuid;
                        chrome.storage.local.set({ userUUID: uuid }, () => resolve(uuid));
                    } else {
                        console.error("Failed to create user:", response.statusText);
                        resolve(null);
                    }
                }
            });
        });
    }

    async function fetchCrawls(uuid) {
        const response = await fetch(`${API_URL}/get-all-crawls`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: uuid }),
        });
        return response.ok ? await response.json() : [];
    }

    async function displayCrawls() {
        const uuid = await getUserUUID();
        if (!uuid) {
            document.getElementById("crawlList").innerHTML = "<tr><td colspan='4'>Failed to create user. Please try again.</td></tr>";
            return;
        }

        const crawls = await fetchCrawls(uuid);
        const crawlList = document.getElementById("crawlList");
        crawlList.innerHTML = '';  // Clear current list

        if (crawls.length === 0) {
            crawlList.innerHTML = "<tr><td colspan='4'>No crawls found.</td></tr>";
        } else {
            crawls.forEach((crawl) => {
                const crawlRow = document.createElement("tr");

                let statusClass = "";
                if (crawl.status === "completed") statusClass = "status-completed";
                else if (crawl.status === "running") statusClass = "status-running";
                else if (crawl.status === "paused") statusClass = "status-paused";

                crawlRow.innerHTML = `
                    <td style="display: flex; align-items: center;">
                        <img src="${crawl.favicon}" alt="favicon" class="favicon" />
                        ${crawl.crawl_name}
                    </td>
                    <td class="${statusClass}">${crawl.status}</td>
                    <td>
                        ${crawl.status === "completed" ? "" : `
                            <i class="${crawl.status === 'paused' ? 'fas fa-play' : 'fas fa-pause'} action-icon toggle-status" 
                                data-id="${crawl.crawl_id}" title="${crawl.status === 'paused' ? 'Resume' : 'Pause'}"></i>
                        `}
                        <i class="fas fa-trash-alt action-icon delete" data-id="${crawl.crawl_id}" title="Delete"></i>
                    </td>
                `;
                crawlList.appendChild(crawlRow);
            });
        }

        document.querySelectorAll(".toggle-status").forEach(button => {
            button.addEventListener("click", () => togglePauseResume(button.dataset.id));
        });
        document.querySelectorAll(".delete").forEach(button => {
            button.addEventListener("click", () => deleteCrawl(button.dataset.id));
        });
    }

    async function createNewCrawl(event) {
        event.preventDefault();
        if (document.getElementById("modeToggle").checked) {
            alert("Client mode is currently unavailable. Please switch back to Server mode.");
            return;
        }

        const uuid = await getUserUUID();
        if (!uuid) {
            console.error("Failed to create crawl due to missing user ID.");
            return;
        }

        const crawlName = document.getElementById("crawlName").value;
        const startUrl = document.getElementById("startUrl").value;
        const crawlDepth = parseInt(document.getElementById("crawlDepth").value);
        const maxLinks = parseInt(document.getElementById("maxLinks").value);
        const followExternal = document.getElementById("followExternal").checked;
        const concurrency = parseInt(document.getElementById("concurrency").value);
        const delay = parseFloat(document.getElementById("delay").value);
        const onlyChildPages = document.getElementById("onlyChildPages").checked;

        const requestBody = {
            user_id: uuid,
            crawl_name: crawlName,
            start_urls: [startUrl],
            max_links: maxLinks,
            follow_external: followExternal,
            depth_limit: crawlDepth,
            concurrent_requests: concurrency,
            delay: delay,
            only_child_pages: onlyChildPages
        };

        const response = await fetch(`${API_URL}/crawl-url/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestBody)
        });
    
        if (response.ok) {
            const result = await response.json();
    
            // Check for the custom header 'user-uuid-update'
            const updatedUUID = response.headers.get("user-uuid-update");
            if (updatedUUID) {
                // Update the userUUID in Chrome storage
                chrome.storage.local.set({ userUUID: updatedUUID });
            }
    
            // Proceed with displaying crawls after creation
            toggleView("crawlListContainer", "newCrawlContainer");
            displayCrawls();
        } else {
            console.error("Failed to create crawl:", response.statusText);
        }
    }

    function toggleModeAvailability() {
        const modeUnavailableMessage = document.getElementById("modeUnavailable");
        if (document.getElementById("modeToggle").checked) {
            modeUnavailableMessage.style.display = "block";
        } else {
            modeUnavailableMessage.style.display = "none";
        }
    }

    async function togglePauseResume(crawlId) {
        const uuid = await getUserUUID();
        const crawls = await fetchCrawls(uuid);
        const crawl = crawls.find(c => c.crawl_id === crawlId);
        const action = crawl.status === "paused" ? "resume" : "pause";
        await fetch(`${API_URL}/${action}-crawl`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ crawl_id: crawlId })
        });
        displayCrawls();
    }

    async function deleteCrawl(crawlId) {
        await fetch(`${API_URL}/delete-crawl`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ crawl_session_id: crawlId })
        });
        displayCrawls();
    }

    function toggleView(showId, hideId) {
        document.getElementById(showId).style.display = "block";
        document.getElementById(hideId).style.display = "none";
    }

    document.getElementById("createCrawlBtn").addEventListener("click", () => {
        chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
            document.getElementById("startUrl").value = tabs[0].url;
            document.getElementById("crawlName").value = tabs[0].title;
        });
        toggleView("newCrawlContainer", "crawlListContainer");
    });

    document.getElementById("refreshCrawls").addEventListener("click", displayCrawls);
    document.getElementById("backToCrawls").addEventListener("click", () => {
        toggleView("crawlListContainer", "newCrawlContainer");
    });

    document.getElementById("modeToggle").addEventListener("change", toggleModeAvailability);
    document.getElementById("newCrawlForm").addEventListener("submit", createNewCrawl);
    displayCrawls();
});
