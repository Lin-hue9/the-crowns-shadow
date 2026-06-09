
// Create floating particles
function createParticles() {
    for(let i = 0; i < 30; i++) {
        let particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.width = Math.random() * 4 + 2 + 'px';
        particle.style.height = particle.style.width;
        particle.style.animationDelay = Math.random() * 8 + 's';
        particle.style.animationDuration = Math.random() * 6 + 5 + 's';
        document.body.appendChild(particle);
    }
}

// Wax seal drip effect
function createWaxDrip(x, y) {
    let drip = document.createElement('div');
    drip.className = 'wax-drip';
    drip.style.left = x + 'px';
    drip.style.top = y + 'px';
    drip.style.width = '30px';
    drip.style.height = '30px';
    document.body.appendChild(drip);
    setTimeout(() => drip.remove(), 1000);
}

// Animate number counting
function animateNumber(element, start, end, duration = 1000) {
    let startTime = null;
    function animate(currentTime) {
        if (!startTime) startTime = currentTime;
        let progress = Math.min((currentTime - startTime) / duration, 1);
        let current = Math.floor(start + (end - start) * progress);
        element.textContent = current;
        if (progress < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
}

// Typewriter effect
function typewriter(element, text, speed = 50) {
    element.textContent = '';
    let i = 0;
    function type() {
        if (i < text.length) {
            element.textContent += text.charAt(i);
            i++;
            setTimeout(type, speed);
        }
    }
    type();
}

// Run on page load
document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    
    // Add wax drip effect to buttons
    document.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', (e) => {
            let rect = btn.getBoundingClientRect();
            createWaxDrip(rect.left + rect.width/2, rect.top + rect.height/2);
        });
    });
});

