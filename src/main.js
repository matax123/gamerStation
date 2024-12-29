



const swiper = new Swiper('.swiper-container', {
  slidesPerView: 3, // Show 3 slides at once
  slidesPerGroup: 1, // Slide 3 slides per click
  spaceBetween: 0, // Spacing between slides
  loop: true, // Enable loop mode
  loopAdditionalSlides: 1,
  loopedSlides: 1,
  effect: 'coverflow', // Enable the coverflow effect
  // loop: true, // Enable loop mode
  coverflowEffect: {
    rotate: 30, // Adjust rotation angle for 3D effect
    stretch: 0, // Disable stretching of slides
    depth: 70, // Adjust depth for 3D effect
    modifier: 1, // Adjust modifier for perspective
    slideShadows: true, // Enable shadows for depth perception
  },
  pagination: {
    el: '.swiper-pagination',
    clickable: true,
  },
  navigation: {
    nextEl: '.swiper-button-next',
    prevEl: '.swiper-button-prev',
  },
  initialSlide: 1,
});


// let lastInput = document.getElementById("last-input");
// let inputData = {"axis": [], "button": []};
let axis = {};
let buttons = {};
let websocket;

function connectWebSocket() {
  websocket = new WebSocket("ws://localhost:8765");

  websocket.onopen = (event) => {
    console.log("WebSocket connected!");
  };

  websocket.onmessage = (event) => {
    try {
      let input = JSON.parse(event.data);
      if (input.type === "axis") axis[input.axis] = input.value;
      if (input.type === "button") buttons[input.button] = input.value;
      console.log("Axis: ", axis);
    } catch (error) {
      console.error("JSON parsing error:", error, event.data);
    }
  };

  websocket.onclose = (event) => {
    console.log("WebSocket disconnected. Reconnecting in 1 second...");
    setTimeout(connectWebSocket, 1000);
  };

  websocket.onerror = (error) => {
    console.error("WebSocket error:", error);
  };
}

connectWebSocket();




async function selectGame(game){
  await pywebview.api.log(game.value);
}


let isProcessing = false;
setInterval(async () => {
  if (isProcessing) return;  // Skip if already processing
  isProcessing = true;

  if (axis[0] < -0.5) {
    swiper.slidePrev();
  }
  if (axis[0] > 0.5) {
    swiper.slideNext();
  }
  if (buttons[0] === 1) {
    await pywebview.api.open_file();
  }
  if (buttons[3] === 1) {
    let result = await pywebview.api.save_path();
    if(result !== null){
      let askName = document.getElementById("askName");
      askName.classList.remove("d-none");

    }
  }

  let result = await pywebview.api.get_images();
  isProcessing = false;
  // lastInput.innerHTML = JSON.stringify({axis, buttons});
}, 5);





async function loadImages() {

}
loadImages();