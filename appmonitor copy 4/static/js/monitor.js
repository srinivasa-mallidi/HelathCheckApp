async function startMonitoring(appId) {

    async function checkApp() {
        document.getElementById("app-status").innerText = "Checking...";
        const res = await fetch(`/api/app/health/${appId}`);
        const data = await res.json();
        document.getElementById("app-status").innerText =
            data.ok ? "✔ Up and Running" : "✖ Down";
    }

    async function checkUsers() {
        const res = await fetch(`/api/app/users/${appId}`);
        const data = await res.json();
        document.getElementById("user-count").innerText =
            `Active Users: ${data.users}`;
    }

    async function checkInterfaces() {
        document.querySelectorAll("tr[data-if]").forEach(async row => {
            const id = row.dataset.if;

            let o = await fetch(`/api/interface/${id}/OUTBOUND`);
            let od = await o.json();
            row.querySelector(".out").innerText =
                od.reachable ? `✔ ${od.total}` : "✖";

            let i = await fetch(`/api/interface/${id}/INBOUND`);
            let idata = await i.json();
            row.querySelector(".in").innerText =
                idata.reachable ? `✔ ${idata.total}` : "✖";
        });
    }

    // initial sequential illusion
    await checkApp();
    await new Promise(r => setTimeout(r, 800));
    await checkUsers();
    await new Promise(r => setTimeout(r, 800));
    await checkInterfaces();

    // continuous background polling
    setInterval(checkApp, 10000);
    setInterval(checkUsers, 5000);
    setInterval(checkInterfaces, 10000);
}
