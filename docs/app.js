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

  Object.entries(attrs).forEach(([k, v]) => {
    if (k === "className") {
      node.className = v;
    } else if (k === "textContent") {
      node.textContent = v;
    } else {
      node.setAttribute(k, v);
    }
  });

  children.forEach((c) => {
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });

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

function renderSignals(signals) {
  const signalsListEl = document.getElementById("signals-list");
  const signalsSectionEl = document.getElementById("signals-section");

  if (!signalsListEl || !signalsSectionEl) return;

  signalsListEl.innerHTML = "";

  if (!signals || !signals.length) {
    signalsSectionEl.style.display = "none";
    return;
  }

  signalsSectionEl.style.display = "block";

  signals.forEach((signal) => {
    const card = el("article", { className: "signal-card" }, [
      el("div", { className: "signal-head" }, [
        el("div", { className: "signal-brand" }, [signal.brand || "Unknown"]),
        el("span", { className: "signal-type" }, [signal.type || "Strategic update"])
      ]),
      el("div", { className: "signal-headline" }, [signal.headline || ""]),
      el("div", { className: "signal-impact" }, [signal.impact || ""])
    ]);

    signalsListEl.appendChild(card);
  });
}

function renderMomentum(momentum) {
  const momentumListEl = document.getElementById("momentum-list");
  const momentumSectionEl = document.getElementById("momentum-section");

  if (!momentumListEl || !momentumSectionEl) return;

  momentumListEl.innerHTML = "";

  if (!momentum || !momentum.length) {
    momentumSectionEl.style.display = "none";
    return;
  }

  momentumSectionEl.style.display = "block";

  const maxCount = Math.max(...momentum.map((item) => item.count), 1);

  momentum.forEach((item) => {
    const widthPercent = Math.max((item.count / maxCount) * 100, 8);

    const card = el("article", { className: "momentum-card" }, [
      el("div", { className: "momentum-head" }, [
        el("div", { className: "momentum-brand" }, [item.brand || "Unknown"]),
        el("div", { className: "momentum-count" }, [`${item.count}`])
      ]),
      el("div", { className: "momentum-bar-track" }, [
        el("div", {
          className: "momentum-bar-fill",
          style: `width: ${widthPercent}%;`
        }, [])
      ])
    ]);

    momentumListEl.appendChild(card);
  });
}

function renderTopicTrends(topicTrends) {
  const trendsListEl = document.getElementById("trends-list");
  const trendsSectionEl = document.getElementById("trends-section");

  if (!trendsListEl || !trendsSectionEl) return;

  trendsListEl.innerHTML = "";

  if (!topicTrends || !topicTrends.length) {
    trendsSectionEl.style.display = "none";
    return;
  }

  trendsSectionEl.style.display = "block";

  topicTrends.forEach((item) => {
    const chip = el("div", { className: "trend-chip" }, [
      el("span", { className: "trend-topic" }, [item.topic || "Topic"]),
      el("span", { className: "trend-count" }, [`${item.count || 0}`])
    ]);

    trendsListEl.appendChild(chip);
  });
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

    renderSignals(data.signals || []);
    renderMomentum(data.momentum || []);
    renderTopicTrends(data.topic_trends || []);

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

    renderSignals([]);
    renderMomentum([]);
    renderTopicTrends([]);
  }
}

function createPressList(items, expanded = false) {
  const visibleCount = expanded
    ? Math.min(items.length, MAX_VISIBLE_ITEMS)
    : Math.min(items.length, DEFAULT_VISIBLE_ITEMS);

  const list = el("ol", { className: "press-list" }, []);

  items.slice(0, visibleCount).forEach((it, index) => {
    const item = el("li", { className: "press-item" }, [
      el("div", { className: "press-item-row" }, [
        el("span", { className: "press-item-number", textContent: `${index + 1}.` }),
        el("div", { className: "press-item-content" }, [
          el("a", { href: it.url, target: "_blank", rel: "noreferrer" }, [it.title]),
          el("span", { className: "item-date" }, [formatDate(it.publish_datetime)])
        ])
      ])
    ]);

    list.appendChild(item);
  });

  return list;
}

function createShowMoreButton(items, listContainer, labelEl) {
  let expanded = false;

  const button = el("button", { type: "button", className: "show-more-btn" }, ["Show more"]);

  button.addEventListener("click", () => {
    expanded = !expanded;

    const newList = createPressList(items, expanded);
    listContainer.innerHTML = "";
    listContainer.appendChild(newList);

    labelEl.textContent = expanded
      ? `Latest ${Math.min(items.length, MAX_VISIBLE_ITEMS)}`
      : `Latest ${Math.min(items.length, DEFAULT_VISIBLE_ITEMS)}`;

    button.textContent = expanded ? "Show less" : "Show more";

    if (!expanded) {
      listContainer.scrollTop = 0;
    }
  });

  return button;
}

function renderBrand(brandName, payload) {
  const statusText = payload.status === "ok" ? "Live" : "Issue";

  const card = el("article", { className: "card" }, [
    el("div", { className: "card-head" }, [
      el("h3", { className: "card-title" }, [brandName]),
      el("span", { className: `status ${payload.status === "ok" ? "ok" : "error"}` }, [
        el("span", { className: "status-dot" }, []),
        el("span", { className: "status-label" }, [statusText])
      ])
    ])
  ]);

  if (payload.status !== "ok") {
    card.appendChild(el("p", { className: "error-text" }, [payload.error || "Could not load data"]));
    return card;
  }

  const items = payload.items || [];
  const latest = items[0];

  const latestBlock = el("div", { className: "latest-block" }, [
    el("div", { className: "section-label" }, ["Latest press release"])
  ]);

  if (latest) {
    latestBlock.appendChild(
      el("a", { href: latest.url, target: "_blank", rel: "noreferrer", className: "latest-link" }, [latest.title])
    );
    latestBlock.appendChild(
      el("div", { className: "latest-date" }, [formatDate(latest.publish_datetime)])
    );
  } else {
    latestBlock.appendChild(el("div", { className: "muted" }, ["No items found"]));
  }

  card.appendChild(latestBlock);

  const initialVisibleCount = Math.min(items.length, DEFAULT_VISIBLE_ITEMS);
  const listLabel = el("div", { className: "section-label list-label" }, [`Latest ${initialVisibleCount}`]);
  card.appendChild(listLabel);

  const listContainer = el("div", { className: "press-list-wrap" }, [
    createPressList(items, false)
  ]);
  card.appendChild(listContainer);

  if (items.length > DEFAULT_VISIBLE_ITEMS) {
    const controls = el("div", { className: "card-controls" }, [
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
