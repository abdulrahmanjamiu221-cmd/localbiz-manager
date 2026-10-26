(function () {
  const rows = new Map();
  const productButtons = Array.from(document.querySelectorAll(".product-choice"));
  const cartRows = document.getElementById("cartRows");
  if (!cartRows) return;

  const centsFrom = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? Math.round(number * 100) : 0;
  };
  const money = (cents) => "₦" + (cents / 100).toLocaleString("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
  const key = () => window.crypto && window.crypto.randomUUID
    ? window.crypto.randomUUID()
    : Date.now().toString(36) + Math.random().toString(36).slice(2);
  let checkoutKey = key();

  function calculate() {
    let subtotal = 0;
    rows.forEach((item) => { subtotal += item.price * item.quantity; });
    const discount = Math.max(0, centsFrom(document.getElementById("discount").value));
    const total = Math.max(0, subtotal - discount);
    const paid = ["cash", "transfer", "card"].reduce((sum, method) => {
      return sum + Math.max(0, centsFrom(document.getElementById("pay-" + method).value));
    }, 0);
    document.getElementById("subtotal").textContent = money(subtotal);
    document.getElementById("discountTotal").textContent = money(discount);
    document.getElementById("total").textContent = money(total);
    document.getElementById("paid").textContent = money(paid);
    document.getElementById("creditDue").textContent = money(Math.max(0, total - paid));
    document.getElementById("checkoutButton").disabled = rows.size === 0 || discount > subtotal || paid > total;
    return {subtotal, discount, total, paid};
  }

  function renderCart() {
    cartRows.replaceChildren();
    rows.forEach((item, id) => {
      const tr = document.createElement("tr");
      const name = document.createElement("td");
      name.textContent = item.name;
      const quantity = document.createElement("td");
      quantity.className = "text-nowrap";
      const less = document.createElement("button");
      less.type = "button";
      less.className = "btn btn-sm btn-light";
      less.textContent = "−";
      less.setAttribute("aria-label", "Remove one " + item.name);
      less.addEventListener("click", () => {
        item.quantity -= 1;
        if (item.quantity <= 0) rows.delete(id);
        renderCart();
      });
      const count = document.createElement("strong");
      count.className = "mx-2";
      count.textContent = item.quantity;
      const more = document.createElement("button");
      more.type = "button";
      more.className = "btn btn-sm btn-light";
      more.textContent = "+";
      more.setAttribute("aria-label", "Add one " + item.name);
      more.disabled = item.quantity >= item.stock;
      more.addEventListener("click", () => {
        if (item.quantity < item.stock) item.quantity += 1;
        renderCart();
      });
      quantity.append(less, count, more);
      const line = document.createElement("td");
      line.className = "text-end fw-semibold";
      line.textContent = money(item.price * item.quantity);
      tr.append(name, quantity, line);
      cartRows.appendChild(tr);
    });
    document.getElementById("cartEmpty").classList.toggle("d-none", rows.size > 0);
    document.getElementById("cartTable").classList.toggle("d-none", rows.size === 0);
    calculate();
  }

  productButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.productId;
      const item = rows.get(id) || {
        id,
        name: button.dataset.name,
        price: centsFrom(button.dataset.price),
        stock: Number(button.dataset.stock),
        quantity: 0
      };
      if (item.quantity < item.stock) {
        item.quantity += 1;
        rows.set(id, item);
      }
      renderCart();
    });
  });

  document.getElementById("productSearch").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLocaleLowerCase();
    productButtons.forEach((button) => {
      const value = (button.dataset.name + " " + button.dataset.sku).toLocaleLowerCase();
      button.hidden = !value.includes(query);
    });
  });
  document.querySelectorAll(".payment-input").forEach((input) => input.addEventListener("input", calculate));
  document.getElementById("discount").addEventListener("input", calculate);

  document.getElementById("checkoutButton").addEventListener("click", async function () {
    const totals = calculate();
    const error = document.getElementById("checkoutError");
    error.classList.add("d-none");
    const customerId = document.getElementById("customer").value;
    if (totals.paid < totals.total && !customerId) {
      error.textContent = "Select a customer for the outstanding credit balance.";
      error.classList.remove("d-none");
      return;
    }
    const button = this;
    button.disabled = true;
    button.textContent = "Saving sale…";
    const payload = {
      items: Array.from(rows.values()).map((item) => ({product_id: item.id, quantity: item.quantity})),
      discount: (totals.discount / 100).toFixed(2),
      customer_id: customerId || null,
      idempotency_key: checkoutKey,
      payments: {}
    };
    ["cash", "transfer", "card"].forEach((method) => {
      const value = Math.max(0, centsFrom(document.getElementById("pay-" + method).value));
      payload.payments[method] = (value / 100).toFixed(2);
    });
    try {
      const response = await fetch("/sales/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.getElementById("csrf-token").value
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to complete sale.");
      window.location.assign(data.redirect);
    } catch (requestError) {
      error.textContent = requestError.message || "Unable to complete sale. Please try again.";
      error.classList.remove("d-none");
      button.disabled = false;
      button.textContent = "Complete sale";
    }
  });

  renderCart();
}());
