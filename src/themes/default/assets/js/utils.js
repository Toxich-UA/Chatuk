let scrolled = true;
let elem = document.getElementById('chat-container');

elem.addEventListener("mouseenter", function () {
  scrolled = false;
});
elem.addEventListener("mouseleave", function () {
  scrolled = true;
});
function updateScroll() {
  if (scrolled) {
    elem.scrollTop = elem.scrollHeight;
  }
}

setInterval(updateScroll,100);