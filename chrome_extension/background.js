chrome.runtime.onInstalled.addListener(() => {
    // Ensure UUID creation on first installation
    chrome.storage.local.get("userUUID", (data) => {
        if (!data.userUUID) {
            const uuid = crypto.randomUUID();
            chrome.storage.local.set({ userUUID: uuid });
        }
    });
});
