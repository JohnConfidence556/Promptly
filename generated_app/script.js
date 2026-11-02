document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('welcomeButton');
  const message = document.getElementById('message');

  if (button && message) {
    button.addEventListener('click', () => {
      message.textContent = 'Welcome! Your app is working.';
    });
  }
});