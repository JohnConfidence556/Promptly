const display = document.querySelector('#main-container #display-area');
let expression = '';

function updateDisplay() {
  display.textContent = expression || '0';
}

function clearDisplay() {
  expression = '';
  updateDisplay();
}

function computeResult() {
  const match = expression.match(/^(-?\d+(?:\.\d+)?)([+\-*\/])(-?\d+(?:\.\d+)?)$/);
  if (!match) {
    return;
  }
  const left = parseFloat(match[1]);
  const right = parseFloat(match[3]);
  const results = {
    '+': left + right,
    '-': left - right,
    '*': left * right,
    '/': right === 0 ? 'Error' : left / right,
  };
  expression = String(results[match[2]]);
  updateDisplay();
}

function handleButtonClick(event) {
  const button = event.target.closest('.button');
  if (!button) {
    return;
  }
  if (button.dataset.action === 'clear') {
    clearDisplay();
    return;
  }
  if (button.dataset.action === 'equals') {
    computeResult();
    return;
  }
  if (button.dataset.op) {
    document.querySelectorAll('.operation-button').forEach((item) => {
      item.classList.remove('active-operation');
    });
    button.classList.add('active-operation');
    expression += button.dataset.op;
  } else if (button.dataset.value) {
    expression += button.dataset.value;
  }
  updateDisplay();
}

function handleKeyPress(event) {
  if (/^[0-9.+\-*\/]$/.test(event.key)) {
    expression += event.key;
    updateDisplay();
  } else if (event.key === 'Enter') {
    computeResult();
  } else if (event.key === 'Escape') {
    clearDisplay();
  }
}

document.querySelector('.keypad-grid').addEventListener('click', handleButtonClick);
document.addEventListener('keydown', handleKeyPress);