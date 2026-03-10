const brands = [
  { key: "virginmediao2", name: "Virgin Media O2", group: "Telecoms", file: "./data/virginmediao2.json" },
  { key: "vodafone", name: "Vodafone", group: "Telecoms", file: "./data/vodafone.json" },
  { key: "ee", name: "EE", group: "Telecoms", file: "./data/ee.json" },
  { key: "three", name: "Three", group: "Telecoms", file: "./data/three.json" },
  { key: "bt", name: "BT", group: "Telecoms", file: "./data/bt.json" },
  { key: "sky", name: "Sky", group: "Telecoms", file: "./data/sky.json" },

  { key: "comparethemarket", name: "Compare the Market", group: "Affiliates", file: "./data/comparethemarket.json" },
  { key: "moneysavingexpert", name: "MoneySavingExpert", group: "Affiliates", file: "./data/moneysavingexpert.json" },
  { key: "uswitch", name: "uSwitch", group: "Affiliates", file: "./data/uswitch.json" },
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
  return isNaN(d.getTime()) ? "Date unavailable" : d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

async function loadBrand(brand) {
  const res = await fetch(brand.file, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${brand.file}: ${res.status}`);
  return await res.json();
}

function renderBrand(brandName, payload) {
  const card = el("article", { class: "card" }, [
    el("div", { class: "card-head" }, [
      el("h3", { class: "card-title" }, [brandName]),
      el("span", { class: `status ${payload.status === "ok" ? "ok" : "error"}` }, [
        payload.status === "ok" ? "Updated" : "Failed"
      ])
    ])
  ]);

  if (payload.status !== "ok") {
    card.appendChild(el("p", { class: "error-text" }, [payload.error || "Could not load data"]));
    return card;
  }

  const items = payload.items || [];
  const latest = items[0];

  const latestBlock = el("div", { class: "latest-block" }, [
    el("div", { class: "section-label" }, ["Latest press release"]),
  ]);

  if (latest) {
    latestBlock.appendChild(
      el("a", { href: latest.url, target: "_blank", rel: "noreferrer", class: "latest-link" }, [latest.title])
    );
    latestBlock.appendChild(
      el("div", { class: "latest-date" }, [formatDate(latest.publish_datetime)])
    );
  } else {
    latestBlock.appendChild(el("div", { class: "muted" }, ["No items found"]));
  }

  card.appendChild(latestBlock);
  card.appendChild(el("div", { class: "section-label list-label" }, ["Latest 10"]));

  const list = el("ol", { class: "press-list" }, []);
  items.slice(0, 10).forEach((it) => {
    list.appendChild(
      el("li", { class: "press-item" }, [
        el("a", { href: it.url, target: "_blank", rel: "noreferrer" }, [it.title]),
        el("span", { class: "item-date" }, [formatDate(it.publish_datetime)])
      ])
    );
  });

  card.appendChild(list);
  return card;
}

async function main() {
  const telecomsContainer = document.getElementById("telecoms-grid");
  const affiliatesContainer = document.getElementById("affiliates-grid");

  telecomsContainer.innerHTML = "";
  affiliatesContainer.innerHTML = "";

  for (const brand of brands) {
    try {
      const payload = await loadBrand(brand);
      const card = renderBrand(brand.name, payload);

      if (brand.group === "Telecoms") {
        telecomsContainer.appendChild(card);
      } else {
        affiliatesContainer.appendChild(card);
      }
    } catch (e) {
      const card = renderBrand(brand.name, { status: "error", error: String(e), items: [] });
      if (brand.group === "Telecoms") {
        telecomsContainer.appendChild(card);
      } else {
        affiliatesContainer.appendChild(card);
      }
    }
  }
}

main();
