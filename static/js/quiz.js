// Quiz modal logic for bonus points after all chores are completed
// Requires quiz_questions to be available globally (imported from backend or as a static file)

let quizHasBeenShownToday = false;

function showQuizModal(personId, onResult) {
    if (quizHasBeenShownToday) return;
    quizHasBeenShownToday = true;
    
    // Filter questions based on person's age
    let questionsToUse = window.quiz_questions;
    if (window.person_ages && personId && window.person_ages[personId]) {
        const age = window.person_ages[personId];
        if (age <= 4) {
            // 4 years old or below: only easy questions (animal sounds)
            questionsToUse = window.quiz_questions.filter(q => q.difficulty === 'easy');
        } else {
            // Above 4 years old: complex questions (animal images, landmarks, facts)
            questionsToUse = window.quiz_questions.filter(q => q.difficulty === 'complex');
        }
    }
    
    // Pick a random question from the filtered set
    const question = questionsToUse[Math.floor(Math.random() * questionsToUse.length)];
    const modal = document.createElement('div');
    modal.id = 'quiz-modal';
    modal.style = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.8);z-index:10001;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML = `
      <div style="background:#fff;color:#222;padding:2em 2em 1.5em 2em;border-radius:18px;max-width:400px;width:90%;text-align:center;position:relative;box-shadow:0 8px 32px rgba(0,0,0,0.25);">
        <h2 style="color:#4CAF50;font-size:1.4em;margin-bottom:1em;">Quiz Time! <span style='font-size:1.2em;'>🧠</span></h2>
        <div id="quiz-question" style="margin-bottom:1em;font-size:1.1em;"></div>
        <div id="quiz-media" style="margin-bottom:1em;"></div>
        <div id="quiz-choices" style="display:flex;flex-direction:column;gap:0.7em;"></div>
        <button id="quiz-skip" style="margin-top:1.2em;background:#eee;color:#222;border:none;padding:0.7em 1.5em;border-radius:8px;cursor:pointer;font-weight:600;">Skip (smaller bonus)</button>
      </div>
    `;
    document.body.appendChild(modal);
    // Fill in question
    document.getElementById('quiz-question').textContent = question.question;
    // Media
    const mediaDiv = document.getElementById('quiz-media');
    if (question.type === 'animal_image' || question.type === 'landmark') {
        mediaDiv.innerHTML = `<img src="${question.image}" alt="quiz" style="max-width:180px;border-radius:12px;box-shadow:0 2px 8px #bbb;">`;
    } else if (question.type === 'animal_sound') {
        // Custom big play button, no duration/volume
        mediaDiv.innerHTML = `
          <button id="quiz-big-play" style="display:flex;align-items:center;justify-content:center;width:90px;height:90px;background:#4CAF50;border:none;border-radius:50%;box-shadow:0 2px 8px #bbb;cursor:pointer;margin:0 auto 18px auto;">
            <svg width="48" height="48" viewBox="0 0 48 48"><circle cx="24" cy="24" r="24" fill="#4CAF50"/><polygon points="18,14 36,24 18,34" fill="#fff"/></svg>
          </button>
        `;
        const playBtn = mediaDiv.querySelector('#quiz-big-play');
        let audio = new Audio(question.sound);
        playBtn.onclick = () => {
            audio.currentTime = 0;
            audio.play();
        };
    } else {
        mediaDiv.innerHTML = '';
    }
  // Choices
  const choicesDiv = document.getElementById('quiz-choices');
  if (question.type === 'animal_sound') {
    choicesDiv.style.flexDirection = 'row';
    choicesDiv.style.justifyContent = 'center';
    choicesDiv.style.gap = '1em';
    question.choices.forEach(choice => {
      const btn = document.createElement('button');
      btn.style = 'background:none;border:none;padding:0;cursor:pointer;';
      btn.onclick = () => {
        document.body.removeChild(modal);
        onResult(choice === question.answer);
      };
      const img = document.createElement('img');
      img.src = choice;
      img.alt = 'animal';
      img.style = 'width:90px;height:90px;object-fit:cover;border-radius:16px;box-shadow:0 2px 8px #bbb;transition:transform 0.1s;';
      img.onmouseover = () => { img.style.transform = 'scale(1.08)'; };
      img.onmouseout = () => { img.style.transform = 'scale(1)'; };
      btn.appendChild(img);
      choicesDiv.appendChild(btn);
    });
  } else {
    question.choices.forEach(choice => {
      const btn = document.createElement('button');
      btn.textContent = choice;
      btn.style = 'background:#4CAF50;color:#fff;border:none;padding:0.7em 1.5em;border-radius:8px;cursor:pointer;font-weight:600;';
      btn.onclick = () => {
        document.body.removeChild(modal);
        onResult(choice === question.answer);
      };
      choicesDiv.appendChild(btn);
    });
  }
    // Skip — requires deliberate hold to prevent accidental dismissal
    const skipBtn = document.getElementById('quiz-skip');
    skipBtn.textContent = 'Skip (hold 2s for smaller bonus)';
    let skipTimer = null;
    let skipProgress = null;

    skipBtn.addEventListener('pointerdown', function() {
        skipBtn.style.transition = 'background 2s linear';
        skipBtn.style.background = '#f59e0b';
        skipTimer = setTimeout(function() {
            document.body.removeChild(modal);
            onResult(false, true);
        }, 2000);
    });
    skipBtn.addEventListener('pointerup', function() {
        clearTimeout(skipTimer);
        skipBtn.style.transition = 'background 0.2s';
        skipBtn.style.background = '#eee';
    });
    skipBtn.addEventListener('pointerleave', function() {
        clearTimeout(skipTimer);
        skipBtn.style.transition = 'background 0.2s';
        skipBtn.style.background = '#eee';
    });
}
