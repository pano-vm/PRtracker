const brands = [
  { key: "vodafone", name: "Vodafone", file: "./data/vodafone.json" },
  { key: "virginmediao2", name: "Virgin Media O2", file: "./data/virginmediao2.json" },
];

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  children.forEach((c) => node.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
  return node;
}

function formatDate(iso) {
  if (!iso) return "Date unavailable";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "Date unavailable" : d.toLocaleString("en-GB");
}

async function loadBrand(brand) {
  const res = await fetch(brand.file, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${brand.file}: ${res.status}`);
  return await res.json();
}

function renderBrand(brandName, payload) {
  const card = el("article", { class: "card" }, [
    el("h2", {}, [brandName]),
  ]);

  if (payload.status !== "ok") {
    card.appendChild(el("p", { class: "error" }, [`Failed: ${payload.error || "Unknown error"}`]));
    return card;
  }

  const items = payload.items || [];
  const latest = items[0];

  card.appendChild(el("div", { class: "latest" }, [
    el("h3", {}, ["Latest"]),
    latest
      ? el("p", {}, [
          el("a", { href: latest.url, target: "_blank", rel: "noreferrer" }, [latest.title]),
          el("span", { class: "muted" }, [` - ${formatDate(latest.publish_datetime)}`]),
        ])
      : el("p", { class: "muted" }, ["No items yet"]),
  ]));

  card.appendChild(el("h3", {}, ["Last 20"]));

  const list = el("ol", { class: "list" }, []);
  items.slice(0, 20).forEach((it) => {
    list.appendChild(el("li", {}, [
      el("a", { href: it.url, target: "_blank", rel: "noreferrer" }, [it.title]),
      el("span", { class: "muted" }, [` - ${formatDate(it.publish_datetime)}`]),
    ]));
  });
  card.appendChild(list);

  if (payload.generated_at) {
    card.appendChild(el("p", { class: "muted small" }, [`Updated: ${formatDate(payload.generated_at)}`]));
  }

  return card;
}

async function main() {
  const container = document.getElementById("brands");
  container.innerHTML = "";

  let newestTimestamp = null;

  for (const b of brands) {
    try {
      const payload = await loadBrand(b);
      if (payload.generated_at) {
        const t = new Date(payload.generated_at).toISOString();
        if (!newestTimestamp || t > newestTimestamp) newestTimestamp = t;
      }
      container.appendChild(renderBrand(b.name, payload));
    } catch (e) {
      container.appendChild(renderBrand(b.name, { status: "error", error: String(e) }));
    }
  }

  document.getElementById("lastUpdated").textContent =
    newestTimestamp ? `Last updated: ${formatDate(newestTimestamp)}` : "";
}

main();
