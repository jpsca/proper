export function ready() {
  var links = document.querySelectorAll(".page_toc a");
  links.forEach(link => {
    link.addEventListener("click", function (event) {
      const pop = event.target.closest(".page_toc");
      if (pop) { pop.hidePopover(); }
    });
  });

  setupTocScrollSpy();

  if (!window.scrollPositions) {
    window.scrollPositions = {};
  }
  window.addEventListener("turbo:before-cache", preserveScroll)
  window.addEventListener("turbo:before-render", restoreScroll)
  window.addEventListener("turbo:render", restoreScroll)
}

function setupTocScrollSpy() {
  const tocLinks = Array.from(document.querySelectorAll('.page_toc a[href^="#"]'));
  if (tocLinks.length === 0) return;

  const linkByHash = new Map();
  const headings = [];
  tocLinks.forEach(link => {
    const id = decodeURIComponent(link.getAttribute("href").slice(1));
    if (!id) return;
    const heading = document.getElementById(id);
    if (!heading) return;
    linkByHash.set(heading, link);
    headings.push(heading);
  });
  if (headings.length === 0) return;

  let current = null;
  const setCurrent = (heading) => {
    if (current === heading) return;
    if (current) {
      const prev = linkByHash.get(current);
      if (prev) prev.removeAttribute("aria-current");
    }
    current = heading;
    if (current) {
      const next = linkByHash.get(current);
      if (next) next.setAttribute("aria-current", "true");
    }
  };

  const visible = new Set();
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) visible.add(entry.target);
      else visible.delete(entry.target);
    });

    if (visible.size > 0) {
      const top = [...visible].sort((a, b) =>
        a.getBoundingClientRect().top - b.getBoundingClientRect().top
      )[0];
      setCurrent(top);
      return;
    }
    // Nothing visible — pick the last heading above the viewport.
    let last = null;
    for (const h of headings) {
      if (h.getBoundingClientRect().top < 1) last = h; else break;
    }
    setCurrent(last || headings[0]);
  }, {
    rootMargin: "-80px 0px -70% 0px",
    threshold: 0,
  });

  headings.forEach(h => observer.observe(h));
}

function preserveScroll () {
  document.querySelectorAll("[data-preserve-scroll]").forEach((element) => {
    scrollPositions[element.id] = element.scrollTop;
  })
}

function restoreScroll (event) {
  document.querySelectorAll("[data-preserve-scroll]").forEach((element) => {
    element.scrollTop = scrollPositions[element.id];
  })

  if (!event.detail.newBody) return
  // event.detail.newBody is the body element to be swapped in.
  // https://turbo.hotwired.dev/reference/events
  event.detail.newBody.querySelectorAll("[data-preserve-scroll]").forEach((element) => {
    element.scrollTop = scrollPositions[element.id];
  })
}
