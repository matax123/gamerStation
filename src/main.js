const gameInput = document.getElementById("gameInput");
const gameSearch = document.getElementById("gameSearch");
const games = document.getElementById("games");
const backendUrl = "http://localhost:8400";

async function loadImages() {
  let result = await fetch(backendUrl + '/get-images', { method: 'POST' });
  let images = await result.json();
  return images;
}

async function loadGames() {
  let result = await fetch(backendUrl + '/get-games', { method: 'POST' });
  let games = await result.json();
  return games;
}

function generateSlide(url) {
  url = "../img/" + url;
  console.log(url)
  return `
    <div class="swiper-slide">
      <img src="${url}" >
      </div>
    </div>
  `
}

async function generateSlides(images, games) {
  let swiperWrapper = document.querySelector('.swiper-wrapper');
  swiperWrapper.innerHTML = '';
  let html = '';
  let gamesDisplayed = 0;
  images.forEach(image => {
    console.log(splitByLastDot(image))
    game = games.find(game => splitByLastDot(game)[0] === splitByLastDot(image)[0]);
    // console.log(game)
    if(game) { html += generateSlide(image); gamesDisplayed++; }
  });
  swiperWrapper.innerHTML = html;
  return gamesDisplayed;
}


document.addEventListener('DOMContentLoaded', async () => {
  let images = await loadImages();
  let games = await loadGames();
  let gamesDisplayed = await generateSlides(images, games);

  new Glide('.glide').mount()

  let swiper;
  if(gamesDisplayed >= 5){
    swiper = new Swiper('.swiper-container', {
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
      navigation: {
        nextEl: '.swiper-button-next',
        prevEl: '.swiper-button-prev',
      },
      initialSlide: 1,
    });
  }
  else{
    swiper = new Swiper('.swiper-container', {
      loop: true,
      navigation: {
        nextEl: '.swiper-button-next',
        prevEl: '.swiper-button-prev',
      },
    });
  }




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


  let isProcessing = false;
let awaitingInput = false;
let imagesPath = [];
setInterval(async () => {
  if (isProcessing && !awaitingInput) return;  // Skip if already processing
  isProcessing = true;

  if (awaitingInput) {
    imagesPath.forEach(imagePath => {
      let name = imagePath.replace('.png', '').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
      if (gameInput.value === name) {
        pywebview.api.log("!!!")
        gameInput.value = "";
        awaitingInput = false;
        gameSearch.classList.add("d-none");
      }
    });
  }

  try {
    if (axis[0] < -0.5) {
      swiper.slidePrev();
    } else if (axis[0] > 0.5) {
      swiper.slideNext();
    }

    if (buttons[0] === 1) {
      await pywebview.api.open_file();
    }

    if (buttons[3] === 1) {
      let filePath = await pywebview.api.save_path();


      if (filePath !== null && games) {
        games.innerHTML = "";
        let html = ''
        imagesPath = await pywebview.api.get_images();
        imagesPath.forEach(imagePath => {
          let name = imagePath.replace('.png', '').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
          let path = 'src/' + imagePath
          let option = `<option value="${name}">`
          html += option
        });


        games.innerHTML = html;
        gameSearch.classList.remove("d-none");
        awaitingInput = true;

      }
    }
  } catch (error) {
    console.error("An error occurred:", error);
  } finally {
    isProcessing = false;
  }
}, 50); // Adjusted interval to 50ms for better efficiency

});




//META FUNCTIONS
function splitByLastDot(str) {
  const lastDotIndex = str.lastIndexOf('.');

  if (lastDotIndex === -1) {
    // No dot found, return the original string and an empty string
    return [str, ""];
  }

  const beforeLastDot = str.substring(0, lastDotIndex);
  const afterLastDot = str.substring(lastDotIndex + 1);

  return [beforeLastDot, afterLastDot];
}