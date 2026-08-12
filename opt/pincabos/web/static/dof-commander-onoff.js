/* PinCabOS-File created by Karots Sugarpie */
(function() {
  const repeatTimers = new Map();

  function getControls() {
    return {
      mode: document.getElementById('dof-test-mode')?.value || 'onoff',
      duration: document.getElementById('dof-test-duration')?.value || '500',
      intensity: document.getElementById('dof-test-intensity')?.value || '255',
      auto: document.getElementById('dof-test-auto-repeat')?.checked || false,
      repeatDelay: document.getElementById('dof-test-repeat-delay')?.value || '500'
    };
  }

  function keyFor(toggle) {
    return (toggle.dataset.controller || 'auto') + '::' + (toggle.dataset.output || '0');
  }

  function setVisual(toggle) {
    const wrap = toggle.closest('.dof-toggle-wrap') || toggle.parentElement;

    let label = null;

    if (wrap) {
      label = wrap.querySelector('.dof-toggle-label');
    }

    if (!label) {
      label = toggle.parentElement.querySelector('.dof-toggle-label');
    }

    if (!label) {
      // Dernier recours : cherche le span frère après le slider.
      const parent = toggle.parentElement;
      if (parent) {
        label = parent.querySelector('span:last-child');
      }
    }

    if (!label) return;

    label.textContent = toggle.checked ? 'ON' : 'OFF';

    label.classList.remove('dof-on', 'dof-off');
    label.classList.add(toggle.checked ? 'dof-on' : 'dof-off');

    if (wrap) {
      wrap.classList.remove('is-on', 'is-off');
      wrap.classList.add(toggle.checked ? 'is-on' : 'is-off');
    }
  }

  async function sendAction(toggle, action, updateLog) {
    const controls = getControls();
    const controller = toggle.dataset.controller || toggle.getAttribute('data-controller') || 'auto';
    const output = toggle.dataset.output || toggle.getAttribute('data-output') || '0';

    const panel = document.getElementById('dof-commander-log-panel');
    const log = document.getElementById('dof-commander-log');

    if (panel) panel.style.display = 'block';

    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    };

    setText('dof-cmd-controller', controller);
    setText('dof-cmd-output', output);
    setText('dof-cmd-action', action);
    setText('dof-cmd-mode', controls.mode);
    setText('dof-cmd-duration', controls.duration + ' ms');

    if (updateLog && log) {
      log.textContent = 'Lancement action ' + action.toUpperCase() + '...';
    }

    try {
      const r = await fetch('/api/dof/commander/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          controller: controller,
          output: output,
          action: action,
          mode: controls.mode,
          duration_ms: controls.duration,
          intensity: controls.intensity
        })
      });

      const data = await r.json();

      if (log) {
        log.textContent = data.log || JSON.stringify(data, null, 2);
        log.scrollTop = log.scrollHeight;
      }
    } catch (e) {
      if (log) log.textContent = 'Erreur action output : ' + e;
    }
  }

  function stopRepeat(toggle) {
    const key = keyFor(toggle);
    if (repeatTimers.has(key)) {
      clearInterval(repeatTimers.get(key));
      repeatTimers.delete(key);
    }
  }

  function startRepeat(toggle) {
    stopRepeat(toggle);

    const controls = getControls();
    const duration = parseInt(controls.duration || '500', 10);
    const delay = parseInt(controls.repeatDelay || '500', 10);
    const interval = Math.max(100, duration + delay);

    const timer = setInterval(() => {
      if (!toggle.checked) {
        stopRepeat(toggle);
        setVisual(toggle);
        return;
      }

      sendAction(toggle, 'on', false);
    }, interval);

    repeatTimers.set(keyFor(toggle), timer);
  }

  function initDofToggles() {
    const toggles = document.querySelectorAll('.dof-output-toggle');

    console.log('PinCabOS DOF Commander toggles found:', toggles.length);

    toggles.forEach(toggle => {
      setVisual(toggle);

      toggle.addEventListener('click', function() {
        // Force immédiat au click, avant même l'événement change.
        setTimeout(() => setVisual(toggle), 0);
      });

      toggle.addEventListener('change', function() {
        setVisual(toggle);

        const controls = getControls();

        if (toggle.checked) {
          sendAction(toggle, 'on', true);

          if (controls.auto) {
            startRepeat(toggle);
          } else {
            stopRepeat(toggle);
          }
        } else {
          stopRepeat(toggle);
          sendAction(toggle, 'off', true);
        }

        // Reforce après la réponse UI/navigateur.
        setTimeout(() => setVisual(toggle), 100);
        setTimeout(() => setVisual(toggle), 500);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', initDofToggles);

  // Si la page est déjà chargée.
  if (document.readyState !== 'loading') {
    initDofToggles();
  }
})();
