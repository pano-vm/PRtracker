const brands = [
  { key: "virginmediao2", name: "Virgin Media O2", group: "Telecoms", file: "./data/virginmediao2.json" },
  { key: "vodafone", name: "Vodafone", group: "Telecoms", file: "./data/vodafone.json" },
  { key: "ee", name: "EE", group: "Telecoms", file: "./data/ee.json" },
  { key: "three", name: "Three", group: "Telecoms", file: "./data/three.json" },
  { key: "bt", name: "BT", group: "Telecoms", file: "./data/bt.json" },
  { key: "sky", name: "Sky", group: "Telecoms", file: "./data/sky.json" },

  { key: "moneysavingexpert", name: "MoneySavingExpert", group: "Affiliates", file: "./data/moneysavingexpert.json" },
  { key: "uswitch", name: "uSwitch", group: "Affiliates", file: "./data/uswitch.json" }
];

const DEFAULT_VISIBLE_ITEMS = 5;
const MAX_VISIBLE_ITEMS = 10;

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  children.forEach((c) => node.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
  return node;
}

function formatDate(iso) {
  if (!iso) return "Date unavailable";
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? "Date unavailable"
    : d.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric"
      });
}

function formatDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString("en-GB", {
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

async function loadOverview() {
  try {
    const response = await fetch("./data/overview.json", { cache: "no-store" });

    if (!response.ok) {
      throw new Error(`Failed to load overview.json: ${response.status}`);
    }

    const data = await response.json();

    const summaryEl = document.getElementById("overview-summary");
    const updatedEl = document.getElementById("overview-updated");
    const lastUpdatedEl = document.getElementById("lastUpdated");

    if (summaryEl) {
      summaryEl.textContent = data.summary || "No overview available.";
    }

    const formattedDate = formatDateTime(data.generated_at);

    if (updatedEl) {
      updatedEl.textContent = formattedDate ? `Updated: ${formattedDate}` : "";
    }

    if (lastUpdatedEl) {
      lastUpdatedEl.textContent = formattedDate ? `Last updated: ${formattedDate}` : "";
    }
  } catch (error) {
    console.error("Failed to load overview:", error);

    const summaryEl = document.getElementById("overview-summary");
    const updatedEl = document.getElementById("overview-updated");

    if (summaryEl) {
      summaryEl.textContent = "Overview unavailable right now.";
    }

    if (updatedEl) {
      updatedEl.textContent = "";
    }
  }
}

function createPressList(items, expanded = false) {
  const visibleCount = expanded ? Math.min(items.length, MAX_VISIBLE_ITEMS) : Math.min(items.length, DEFAULT_VISIBLE_ITEMS);
  const list = el("ol", { class: "press-list" }, []);

  items.slice(0, visibleCount).forEach((it) => {
    list.appendChild(
      el("li", { class: "press-item" }, [
        el("a", { href: it.url, target: "_blank", rel: "noreferrer" }, [it.title]),
        el("span", { class: "item-date" }, [formatDate(it.publish_datetime)])
      ])
    );
  });

  return list;
}

function createShowMoreButton(items, listContainer, labelEl) {
  let expanded = false;

  const button = el("button", { type: "button", class: "show-more-btn" }, ["Show more"]);

  button.addEventListener("click", () => {
    expanded = !expanded;

    const newList = createPressList(items, expanded);
    listContainer.innerHTML = "";
    listContainer.appendChild(newList);

    labelEl.textContent = expanded ? `Latest ${Math.min(items.length, MAX_VISIBLE_ITEMS)}` : `Latest ${DEFAULT_VISIBLE_ITEMS}`;
    button.textContent = expanded ? "Show less" : "Show more";

    if (!expanded) {
      listContainer.scrollTop = 0;
    }
  });

  return button;
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
    el("div", { class: "section-label" }, ["Latest press release"])
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

  const initialVisibleCount = Math.min(items.length, DEFAULT_VISIBLE_ITEMS);
  const listLabel = el("div", { class: "section-label list-label" }, [`Latest ${initialVisibleCount}`]);
  card.appendChild(listLabel);

  const listContainer = el("div", { class: "press-list-wrap" }, [
    createPressList(items, false)
  ]);
  card.appendChild(listContainer);

  if (items.length > DEFAULT_VISIBLE_ITEMS) {
    const controls = el("div", { class: "card-controls" }, [
      createShowMoreButton(items, listContainer, listLabel)
    ]);
    card.appendChild(controls);
  }

  return card;
}

async function main() {
  const telecomsContainer = document.getElementById("telecoms-grid");
  const affiliatesContainer = document.getElementById("affiliates-grid");

  telecomsContainer.innerHTML = "";
  affiliatesContainer.innerHTML = "";

  await loadOverview();

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
