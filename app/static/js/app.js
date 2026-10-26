document.addEventListener("submit", function (event) {
  const button = event.submitter;
  const message = event.target.dataset.confirm || (button && button.dataset.confirm);
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
