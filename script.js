let multiplier = 1.00;
let playing = false;
let crashed = false;

const mult = document.getElementById("multiplier");
const plane = document.querySelector(".plane");
const result = document.getElementById("result");

document.getElementById("bet").onclick = startGame;
document.getElementById("cashout").onclick = cashout;

function startGame() {

    if (playing) return;

    multiplier = 1.00;
    playing = true;
    crashed = false;

    result.innerHTML = "";
    plane.style.transform = "translate(0px,0px)";

    const end = Math.random() * 19 + 1;

    const timer = setInterval(() => {

        if (crashed) {
            clearInterval(timer);
            return;
        }

        multiplier += 0.03;

        mult.innerHTML = multiplier.toFixed(2) + "x";

        plane.style.transform =
            `translate(${multiplier*12}px,-${multiplier*5}px)`;

        if (multiplier >= end) {

            crashed = true;
            playing = false;

            result.innerHTML = "💥 Літак розбився!";
        }

    },100);

}

function cashout(){

    if(!playing) return;

    playing=false;
    crashed=true;

    result.innerHTML=
        "🎉 Ти забрав виграш на "+multiplier.toFixed(2)+"x";
}
