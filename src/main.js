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
  return `
    <div class="swiper-slide">
      <img src="${url}" >
    </div>
  `
}

async function generateSlides(images, games) {
  let swiperWrapper = document.querySelector('.swiper-wrapper');
  swiperWrapper.innerHTML = '';
  let html = '';
  let gamesDisplayed = [];
  images.forEach(image => {
    game = games.find(game => splitByLastDot(game)[0] === splitByLastDot(image)[0]);
    if (game) { html += generateSlide(image); gamesDisplayed.push(game); }
  });
  swiperWrapper.innerHTML = html;
  return gamesDisplayed;
}


document.addEventListener('DOMContentLoaded', async () => {
  let images = await loadImages();
  let games = await loadGames();
  let gamesDisplayed = await generateSlides(images, games);


  let swiper;
  if (gamesDisplayed.length >= 5) {
    swiper = new Swiper('.swiper-container', {
      slidesPerView: 3, // Show 3 slides at once
      slidesPerGroup: 1, // Slide 3 slides per click
      spaceBetween: 0, // Spacing between slides
      loop: true, // Enable loop mode
      loopAdditionalSlides: 1,
      loopedSlides: 1,
      effect: 'coverflow', // Enable the coverflow effect
      coverflowEffect: {
        rotate: 30, // Adjust rotation angle for 3D effect
        stretch: 0, // Disable stretching of slides
        depth: 70, // Adjust depth for 3D effect
        modifier: 1, // Adjust modifier for perspective
        slideShadows: true, // Show shadows for better
      },
      navigation: {
        nextEl: '.swiper-button-next',
        prevEl: '.swiper-button-prev',
      },
      initialSlide: 1,
    });
  }
  else {
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
  let paused = false;

  function connectWebSocket() {
    websocket = new WebSocket("ws://localhost:8765");

    websocket.onopen = (event) => {
      console.log("WebSocket connected!");
    };

    websocket.onmessage = async (event) => {
      try {
        let input = JSON.parse(event.data);
        if (input.type === "axis") axis[input.axis] = input.value;
        if (input.type === "button") buttons[input.button] = input.value;
        if (axis[0] < -0.5) {
          swiper.slidePrev();
        } else if (axis[0] > 0.5) {
          swiper.slideNext();
        }

        if (buttons[0] === 1) {
          if(paused) return;
          let gameOpened = await checkGameOpened();          
          if (gameOpened == true) return;

          let game = indexToGame(swiper.realIndex, gamesDisplayed);
          paused = true;
          openGame(game);
          await sleep(3000);
          paused = false;
        }
      } catch (error) {
        console.error("JSON parsing error:", error, event.data);
      }
    };

    websocket.onclose = (event) => {
      setTimeout(connectWebSocket, 1000);
    };

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  }

  connectWebSocket();

  async function checkGameOpened() {
    let result = await fetch(backendUrl + '/check-game', { method: 'POST' });
    let gameOpened = await result.text();
    if(gameOpened == "false") return false;
    else return true;
  }
});




//META FUNCTIONS
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

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

function indexToGame(index, gamesDisplayed) {
  console.log(index)
  console.log(gamesDisplayed)
  if(index === gamesDisplayed.length - 1) return gamesDisplayed[0];
  else return gamesDisplayed[index + 1];
}

async function openGame(game) {
  const data = { file_name: game }; // Create the object ONLY ONCE
  await fetch(backendUrl + '/open-file', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json' // Important: Set the Content-Type header
    },
    body: JSON.stringify(data) // Stringify the object once
  });
}