/* Training — аккаунт. Подключён на главной и во всех тренажёрах.
   - кнопка аккаунта в верхней панели и окно входа / регистрации по почте;
   - прогресс хранится в аккаунте (backend/app.py), а localStorage служит только копией;
   - без входа: не больше 5 решённых задач (калькулятор — без ограничений),
     материалы и PDF размыты и закрыты замком. */
(function () {
  'use strict';

  /* ================= настройки ================= */
  // Когда сайт открыт локально (http://localhost:8000), запросы идут на сервер,
  // запущенный командой «python backend/app.py».
  // Когда бэкенд появится на хостинге, впиши сюда его адрес, например 'https://training-api.example.com'.
  const PRODUCTION_API_URL = '';
  const LOCAL_API_URL = 'http://127.0.0.1:5000';
  const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  const API_URL = isLocal ? LOCAL_API_URL : PRODUCTION_API_URL;

  // Пока адреса бэкенда нет (на GitHub Pages, пока сервер не выложен на хостинг),
  // аккаунты и ограничения выключены, и сайт работает как раньше.
  if (!API_URL) return;

  const GUEST_LIMIT = 5;                                  // сколько задач можно решить без входа
  const TOKEN_KEY = 'training-auth-token';                // токен сессии после входа
  const GUEST_GEN_KEY = 'training-guest-generated';       // задачи из генератора, решённые без входа
  const UNSENT_KEY = 'training-progress-unsent';          // прогресс, который ещё не дошёл до сервера
  const PROGRESS_KEYS = ['limits-progress-v1', 'deriv-progress-v1', 'integrals-progress-v1'];

  // Мост к тренажёру: его создаёт сам тренажёр (limits.html и др.), на главной его нет
  const bridge = window.TrainerBridge || null;

  let user = null;         // { email, name, created_at }, когда вошли
  let checked = false;     // успели ли проверить сохранённый токен на сервере
  let offline = false;     // сервер не ответил — не наказываем вошедшего пользователя ограничениями
  let mode = 'login';      // вкладка в окне: 'login' или 'register'
  let pending = null;      // { email, password } — для повторной отправки письма

  /* ================= localStorage ================= */
  function readStore(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function writeStore(key, value) {
    try {
      if (value == null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (e) {}
  }
  function getToken() { return readStore(TOKEN_KEY) || ''; }
  function readProgress(key) {
    try { return JSON.parse(readStore(key) || '{}') || {}; } catch (e) { return {}; }
  }
  function writeProgress(key, data) { writeStore(key, JSON.stringify(data || {})); }
  function countSolved(data) { return Object.keys(data).filter(function (k) { return data[k]; }).length; }

  /* ================= запросы к API ================= */
  async function api(path, method, body) {
    const headers = {};
    const token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (body) headers['Content-Type'] = 'application/json';

    const response = await fetch(API_URL + path, {
      method: method || 'GET',
      headers: headers,
      body: body ? JSON.stringify(body) : undefined,
      keepalive: method === 'POST' // прогресс успеет уйти, даже если вкладку сразу закрыли
    });
    let data = {};
    try { data = await response.json(); } catch (e) {}
    return { ok: response.ok, status: response.status, data: data };
  }

  /* ================= разметка: кнопка и окно ================= */
  const ICON_USER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="8.5" r="3.8"/><path d="M4.8 20a7.2 7.2 0 0 1 14.4 0"/></svg>';
  const ICON_LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="10.5" width="14" height="10" rx="2.6"/><path d="M8.2 10.5V7.8a3.8 3.8 0 0 1 7.6 0v2.7"/><path d="M12 14.6v2"/></svg>';
  const ICON_CLOSE = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>';

  const accountBtn = document.createElement('button');
  accountBtn.className = 'account-btn';
  accountBtn.type = 'button';
  accountBtn.setAttribute('aria-haspopup', 'dialog');
  accountBtn.innerHTML = ICON_USER.replace('<svg', '<svg class="account-btn__icon"') +
    '<span class="account-btn__ava" aria-hidden="true"></span><span class="account-btn__text">Войти</span>';
  const themeBtn = document.getElementById('themeBtn');
  if (themeBtn) themeBtn.before(accountBtn);

  const dialog = document.createElement('dialog');
  dialog.className = 'auth';
  dialog.setAttribute('aria-labelledby', 'authTitle');
  dialog.innerHTML = `
  <div class="auth__in glass" data-sheen>
    <button class="auth__close" type="button" data-auth-close aria-label="Закрыть">${ICON_CLOSE}</button>
    <div class="auth__head">
      <p class="auth__eyebrow">Training</p>
      <h2 class="auth__title" id="authTitle">Вход</h2>
    </div>
    <p class="auth__notice" id="authNotice" hidden></p>

    <form class="auth__form" id="authForm" novalidate>
      <div class="auth__tabs" role="group" aria-label="Вход или регистрация">
        <button type="button" data-mode="login" aria-pressed="true">Вход</button>
        <button type="button" data-mode="register" aria-pressed="false">Регистрация</button>
      </div>
      <label class="field"><span>Почта</span><input name="email" type="email" autocomplete="email" inputmode="email" autocapitalize="off" spellcheck="false" maxlength="254" required></label>
      <label class="field"><span>Пароль</span><input name="password" type="password" autocomplete="current-password" maxlength="100" required></label>
      <p class="auth__hint" id="authHint" hidden>Пароль — не короче 6 символов. После регистрации придёт письмо со ссылкой: без подтверждения почты войти нельзя.</p>
      <p class="auth__error" id="authError" role="alert" hidden></p>
      <button class="lq-btn lq-btn--primary auth__submit" id="authSubmit" type="submit">Войти</button>
      <button class="auth__link" id="authResend" type="button" hidden>Отправить письмо ещё раз</button>
      <button class="auth__link" id="authForgotLink" type="button">Забыл пароль?</button>
    </form>

    <form class="auth__form" id="forgotForm" novalidate hidden>
      <p class="auth__note">Введи почту, с которой регистрировался. Пришлём ссылку, по которой можно придумать новый пароль.</p>
      <label class="field"><span>Почта</span><input name="email" type="email" autocomplete="email" inputmode="email" autocapitalize="off" spellcheck="false" maxlength="254" required></label>
      <p class="auth__error" id="forgotError" role="alert" hidden></p>
      <button class="lq-btn lq-btn--primary auth__submit" id="forgotSubmit" type="submit">Отправить ссылку</button>
      <button class="auth__link" data-back-to-login type="button">Вспомнил пароль — войти</button>
    </form>

    <form class="auth__form" id="resetForm" novalidate hidden>
      <p class="auth__note">Придумай новый пароль — не короче 6 символов. После смены ты сразу войдёшь, а на других устройствах аккаунт выйдет.</p>
      <label class="field"><span>Новый пароль</span><input name="password" type="password" autocomplete="new-password" maxlength="100" required></label>
      <label class="field"><span>Повтори пароль</span><input name="repeat" type="password" autocomplete="new-password" maxlength="100" required></label>
      <p class="auth__error" id="resetError" role="alert" hidden></p>
      <button class="lq-btn lq-btn--primary auth__submit" id="resetSubmit" type="submit">Сохранить пароль</button>
      <button class="auth__link" id="resetToForgot" type="button" hidden>Запросить новую ссылку</button>
    </form>

    <div class="auth__sent" id="authSent" hidden>
      <div class="auth__mail" aria-hidden="true">@</div>
      <p>Мы отправили письмо на <b id="authSentEmail"></b>. Открой ссылку из письма, чтобы подтвердить почту, а потом войди.</p>
      <p class="auth__note">Письма нет? Проверь папку «Спам» или отправь ещё раз через минуту.</p>
      <div class="auth__row">
        <button class="lq-btn lq-btn--primary" id="authToLogin" type="button">Я подтвердил, войти</button>
        <button class="lq-btn" id="authSentResend" type="button">Отправить ещё раз</button>
      </div>
    </div>

    <div class="auth__profile" id="authProfile" hidden>
      <div class="auth__person">
        <div class="auth__ava" id="authAvatar" aria-hidden="true"></div>
        <div>
          <p class="auth__name" id="authName"></p>
          <p class="auth__sub" id="authEmail"></p>
        </div>
      </div>
      <p class="auth__note" id="authStats"></p>
      <button class="lq-btn" id="logoutBtn" type="button">Выйти</button>
    </div>
  </div>`;
  document.body.appendChild(dialog);

  const $ = function (id) { return document.getElementById(id); };
  const form = $('authForm');
  const tabs = dialog.querySelectorAll('.auth__tabs button');
  const emailInput = form.elements.email;
  const passwordInput = form.elements.password;
  const submitBtn = $('authSubmit');

  /* ================= кнопка в панели ================= */
  function paintButton() {
    const text = accountBtn.querySelector('.account-btn__text');
    const ava = accountBtn.querySelector('.account-btn__ava');
    let label;
    if (user) {
      accountBtn.dataset.state = 'in';
      text.textContent = user.name;
      ava.textContent = user.name.charAt(0).toUpperCase();
      label = 'Аккаунт: ' + user.email;
    } else {
      accountBtn.dataset.state = 'out';
      text.textContent = 'Войти';
      label = 'Войти или зарегистрироваться';
    }
    accountBtn.setAttribute('aria-label', label);
    accountBtn.title = label;
  }

  /* ================= окно входа ================= */
  // Какую часть окна показать: 'form' (вход/регистрация), 'sent' (проверь почту),
  // 'profile' (аккаунт), 'forgot' (забыл пароль), 'reset' (новый пароль)
  function showView(view) {
    form.hidden = view !== 'form';
    $('authSent').hidden = view !== 'sent';
    $('authProfile').hidden = view !== 'profile';
    $('forgotForm').hidden = view !== 'forgot';
    $('resetForm').hidden = view !== 'reset';
  }

  function setMode(newMode) {
    mode = newMode;
    const isLogin = mode === 'login';
    $('authTitle').textContent = isLogin ? 'Вход' : 'Регистрация';
    submitBtn.textContent = isLogin ? 'Войти' : 'Зарегистрироваться';
    passwordInput.autocomplete = isLogin ? 'current-password' : 'new-password';
    $('authHint').hidden = isLogin;
    $('authResend').hidden = true;
    $('authForgotLink').hidden = !isLogin;
    tabs.forEach(function (tab) { tab.setAttribute('aria-pressed', String(tab.dataset.mode === mode)); });
    showError('');
  }

  function showError(message) {
    $('authError').textContent = message;
    $('authError').hidden = !message;
  }

  // Сообщение сверху окна: kind — 'info' (по умолчанию), 'ok' или 'warn'
  function showNotice(message, kind) {
    const box = $('authNotice');
    box.textContent = message || '';
    box.hidden = !message;
    box.dataset.kind = kind || 'info';
  }

  function formatDate(text) {
    // сервер присылает время в UTC без часового пояса: "2026-11-08T14:52:32"
    const date = new Date(text + 'Z');
    if (isNaN(date)) return '';
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function totalSolved() {
    return PROGRESS_KEYS.reduce(function (sum, key) { return sum + countSolved(readProgress(key)); }, 0);
  }

  // Открыть окно. newMode — 'login' или 'register', notice — сообщение сверху
  function openDialog(newMode, notice, kind) {
    showNotice(notice, kind);
    if (user) {
      showView('profile');
      $('authTitle').textContent = 'Аккаунт';
      $('authName').textContent = user.name;
      $('authEmail').textContent = user.email;
      $('authAvatar').textContent = user.name.charAt(0).toUpperCase();
      const since = formatDate(user.created_at);
      $('authStats').textContent = 'Решено задач: ' + totalSolved() + '. Прогресс хранится в аккаунте.' +
        (since ? ' Аккаунт создан ' + since : '');
    } else {
      showView('form');
      setMode(newMode || mode);
    }
    if (!dialog.open) dialog.showModal();
    if (!user) emailInput.focus();
  }

  function showSent(email) {
    showNotice('');
    showView('sent');
    $('authTitle').textContent = 'Проверь почту';
    $('authSentEmail').textContent = email;
  }

  /* ================= регистрация, вход, письмо ================= */
  function serverDownMessage() {
    return isLocal ? 'Сервер не отвечает. Запусти бэкенд: python backend/app.py' : 'Сервер не отвечает, попробуй позже';
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) {
      showError('Введи почту и пароль');
      return;
    }

    submitBtn.disabled = true;
    showError('');
    $('authResend').hidden = true;
    try {
      const res = await api(mode === 'login' ? '/api/login' : '/api/register', 'POST', { email: email, password: password });
      pending = { email: email, password: password };
      if (res.ok && mode === 'register') {
        passwordInput.value = '';
        showSent(res.data.email || email);
      } else if (res.ok) {
        await onLoggedIn(res.data.token, res.data.user);
      } else {
        showError(res.data.error || 'Что-то пошло не так, попробуй ещё раз');
        // почта не подтверждена или письмо не ушло — предлагаем отправить ещё раз
        $('authResend').hidden = !(res.data.code === 'not_confirmed' || res.data.code === 'mail_failed');
      }
    } catch (err) {
      showError(serverDownMessage());
    } finally {
      submitBtn.disabled = false;
    }
  });

  async function resendMail() {
    if (!pending) return;
    try {
      const res = await api('/api/resend', 'POST', pending);
      const message = res.data.message || res.data.error || 'Что-то пошло не так';
      if (form.hidden) {
        showNotice(message, res.ok ? 'ok' : 'warn');
      } else if (res.ok) {
        showSent(pending.email);
        showNotice(message, 'ok');
      } else {
        showError(message);
      }
    } catch (e) {
      showNotice(serverDownMessage(), 'warn');
    }
  }
  $('authResend').addEventListener('click', resendMail);
  $('authSentResend').addEventListener('click', resendMail);
  $('authToLogin').addEventListener('click', function () {
    showView('form');
    setMode('login');
    showNotice('');
    if (pending) emailInput.value = pending.email;
    passwordInput.focus();
  });

  /* ================= забыл пароль ================= */
  const forgotForm = $('forgotForm');
  const resetForm = $('resetForm');
  let resetCode = ''; // код из ссылки в письме (?reset=...)

  function showFormError(id, message) {
    $(id).textContent = message;
    $(id).hidden = !message;
  }

  function showForgot(email) {
    showNotice('');
    showView('forgot');
    $('authTitle').textContent = 'Восстановление пароля';
    showFormError('forgotError', '');
    forgotForm.elements.email.value = email || '';
    forgotForm.elements.email.focus();
  }

  $('authForgotLink').addEventListener('click', function () { showForgot(emailInput.value.trim()); });
  dialog.querySelectorAll('[data-back-to-login]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      showNotice('');
      showView('form');
      setMode('login');
      emailInput.focus();
    });
  });

  forgotForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    const email = forgotForm.elements.email.value.trim();
    if (!email) {
      showFormError('forgotError', 'Введи почту');
      return;
    }

    $('forgotSubmit').disabled = true;
    showFormError('forgotError', '');
    try {
      const res = await api('/api/forgot', 'POST', { email: email });
      if (res.ok) showNotice(res.data.message, 'ok');
      else showFormError('forgotError', res.data.error || 'Что-то пошло не так, попробуй ещё раз');
    } catch (err) {
      showFormError('forgotError', serverDownMessage());
    } finally {
      $('forgotSubmit').disabled = false;
    }
  });

  // Пришли по ссылке из письма — показываем окно «Новый пароль»
  function showReset(code) {
    resetCode = code;
    showNotice('');
    showView('reset');
    $('authTitle').textContent = 'Новый пароль';
    resetForm.reset();
    showFormError('resetError', '');
    $('resetToForgot').hidden = true;
    if (!dialog.open) dialog.showModal();
    resetForm.elements.password.focus();
  }
  $('resetToForgot').addEventListener('click', function () { showForgot(''); });

  resetForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    const password = resetForm.elements.password.value;
    if (password !== resetForm.elements.repeat.value) {
      showFormError('resetError', 'Пароли не совпадают');
      return;
    }

    $('resetSubmit').disabled = true;
    showFormError('resetError', '');
    try {
      const res = await api('/api/reset', 'POST', { code: resetCode, password: password });
      if (res.ok) {
        resetCode = '';
        // если в этом браузере был вход в другой аккаунт, его прогресс в новый аккаунт не переносим
        if (user && user.email !== res.data.user.email) {
          PROGRESS_KEYS.forEach(function (key) { writeStore(key, null); });
        }
        await onLoggedIn(res.data.token, res.data.user);
        openDialog(null, res.data.message, 'ok');
      } else {
        showFormError('resetError', res.data.error || 'Что-то пошло не так, попробуй ещё раз');
        $('resetToForgot').hidden = res.data.code !== 'bad_code';
      }
    } catch (err) {
      showFormError('resetError', serverDownMessage());
    } finally {
      $('resetSubmit').disabled = false;
    }
  });

  async function onLoggedIn(token, newUser) {
    writeStore(TOKEN_KEY, token);
    user = newUser;
    offline = false;
    form.reset();
    // задачи, решённые до входа, переносим в аккаунт
    await pullProgress(true);
    paintAll();
    dialog.close();
  }

  $('logoutBtn').addEventListener('click', async function () {
    await pushUnsent(); // перед выходом досылаем несохранённый прогресс
    try { await api('/api/logout', 'POST'); } catch (e) {}
    writeStore(TOKEN_KEY, null);
    writeStore(UNSENT_KEY, null);
    user = null;
    // прогресс принадлежит аккаунту — в браузере после выхода его не оставляем
    PROGRESS_KEYS.forEach(function (key) { writeStore(key, null); });
    writeStore(GUEST_GEN_KEY, null);
    applyProgressToPage();
    paintAll();
    dialog.close();
  });

  /* ================= прогресс в аккаунте ================= */
  // Забрать прогресс с сервера. mergeLocal = true — добавить к нему задачи, решённые до входа.
  async function pullProgress(mergeLocal) {
    let res;
    try { res = await api('/api/progress'); } catch (e) { return; }
    if (!res.ok) return;
    const server = res.data.progress || {};
    PROGRESS_KEYS.forEach(function (key) {
      let data = server[key] || {};
      if (mergeLocal) {
        const merged = Object.assign({}, data, readProgress(key));
        if (countSolved(merged) !== countSolved(data)) pushProgressNow(key, merged);
        data = merged;
      }
      writeProgress(key, data);
    });
    writeStore(GUEST_GEN_KEY, null);
    applyProgressToPage();
  }

  // Показать новый прогресс на текущей странице
  function applyProgressToPage() {
    if (bridge) bridge.setDone(readProgress(bridge.key));
    else window.dispatchEvent(new Event('storage')); // главная перерисует полоски прогресса (site.js)
  }

  // Список тренажёров, прогресс которых ещё не дошёл до сервера.
  // Хранится в localStorage, поэтому не теряется, даже если сразу закрыть вкладку
  // или пропал интернет: отправится при следующем открытии сайта.
  function readUnsent() {
    try { return JSON.parse(readStore(UNSENT_KEY) || '[]') || []; } catch (e) { return []; }
  }
  function markUnsent(key, isUnsent) {
    const list = readUnsent().filter(function (k) { return k !== key; });
    if (isUnsent) list.push(key);
    writeStore(UNSENT_KEY, list.length ? JSON.stringify(list) : null);
  }

  async function pushProgressNow(key, data) {
    try {
      const res = await api('/api/progress', 'POST', { key: key, data: data });
      if (res.ok) markUnsent(key, false);
    } catch (e) {
      // нет связи — ключ остаётся в списке неотправленных
    }
  }

  // Отправить всё, что не дошло в прошлый раз (берём свежие данные из localStorage)
  async function pushUnsent() {
    const list = readUnsent();
    for (const key of list) await pushProgressNow(key, readProgress(key));
  }

  // Отправка с небольшой задержкой: несколько отметок подряд уйдут одним запросом
  const pushTimers = {};
  function pushProgress(key, data) {
    markUnsent(key, true);
    clearTimeout(pushTimers[key]);
    pushTimers[key] = setTimeout(function () { pushProgressNow(key, data); }, 400);
  }

  // Тренажёр сообщает о каждом сохранении прогресса (функция save() в тренажёре)
  if (bridge) {
    bridge.onSave = function (data) {
      if (user) pushProgress(bridge.key, data);
      paintGuestNote();
    };
  }

  // «Сбросить весь прогресс» на главной (site.js) — сбрасываем и в аккаунте
  document.addEventListener('training:reset', function () {
    if (user) PROGRESS_KEYS.forEach(function (key) { pushProgressNow(key, {}); });
  });

  /* ================= ограничения без входа ================= */
  function isGuest() {
    if (user) return false;
    // токен есть, но сервер ещё не ответил или недоступен — пока не ограничиваем
    if (getToken() && (!checked || offline)) return false;
    return true;
  }

  function guestSolved() {
    return totalSolved() + (Number(readStore(GUEST_GEN_KEY)) || 0);
  }

  // Это попытка проверить ответ? (кнопка «Проверить», Enter в поле ответа, вариант ответа)
  function isCheckAction(e) {
    const target = e.target;
    if (!bridge || !target.closest || !target.closest('#main')) return false;
    if (bridge.mode() === 'calc') return false; // калькулятор доступен всем
    if (e.type === 'click') return !!target.closest('#chk, [data-c]');
    return e.key === 'Enter' && target.matches('input.ans');
  }

  const countedGenTasks = new WeakSet();
  function onCheckAttempt(e) {
    if (!isCheckAction(e)) return;
    if (isGuest() && guestSolved() >= GUEST_LIMIT) {
      e.preventDefault();
      e.stopImmediatePropagation(); // ответ даже не проверяется
      openDialog('register', 'Без входа можно решить ' + GUEST_LIMIT + ' задач, и ты их уже решил. Зарегистрируйся, чтобы продолжить: решённые задачи перенесутся в аккаунт.', 'warn');
      return;
    }
    // ответ проверится обработчиком тренажёра; потом считаем верную задачу из генератора
    const genTask = bridge.mode() === 'gen' ? bridge.genTask() : null;
    setTimeout(function () {
      const correct = document.querySelector('#main .fb.ok');
      if (isGuest() && genTask && correct && !countedGenTasks.has(genTask)) {
        countedGenTasks.add(genTask);
        writeStore(GUEST_GEN_KEY, String((Number(readStore(GUEST_GEN_KEY)) || 0) + 1));
      }
      paintGuestNote();
    }, 0);
  }
  // capture: true — наш обработчик срабатывает раньше обработчиков тренажёра
  document.addEventListener('click', onCheckAttempt, true);
  document.addEventListener('keydown', onCheckAttempt, true);

  // Плашка «без входа решено N из 5» в боковой панели тренажёра
  let guestNote = null;
  const aside = document.querySelector('.wrap > aside');
  if (aside) {
    guestNote = document.createElement('div');
    guestNote.className = 'guest-note';
    guestNote.hidden = true;
    const tools = aside.querySelector('.tools');
    if (tools) tools.after(guestNote); else aside.prepend(guestNote);
    guestNote.addEventListener('click', function (e) {
      if (e.target.closest('button')) openDialog('register');
    });
  }

  function paintGuestNote() {
    if (!guestNote) return;
    guestNote.hidden = !isGuest();
    if (guestNote.hidden) return;
    const n = Math.min(guestSolved(), GUEST_LIMIT);
    const full = n >= GUEST_LIMIT;
    guestNote.classList.toggle('is-full', full);
    guestNote.innerHTML =
      '<div class="guest-note__bar"><i style="width:' + (100 * n / GUEST_LIMIT) + '%"></i></div>' +
      '<p>' + (full
        ? 'Лимит без входа исчерпан: решено ' + n + ' из ' + GUEST_LIMIT + '. Калькулятор работает и дальше.'
        : 'Без входа решено ' + n + ' из ' + GUEST_LIMIT + ' задач. Калькулятор — без ограничений.') + '</p>' +
      '<button class="lq-btn lq-btn--sm' + (full ? ' lq-btn--primary' : '') + '" type="button">Зарегистрироваться</button>';
  }

  // Материалы и PDF: без входа размыты и закрыты замком
  const LOCKED_SELECTOR = '.mat .doc, .doclinks, .side-docs';
  function paintLocks() {
    const locked = isGuest();
    document.querySelectorAll(LOCKED_SELECTOR).forEach(function (box) {
      box.classList.toggle('is-locked', locked);
      box.querySelectorAll('a').forEach(function (a) {
        if (locked) { a.setAttribute('tabindex', '-1'); a.setAttribute('aria-hidden', 'true'); }
        else { a.removeAttribute('tabindex'); a.removeAttribute('aria-hidden'); }
      });
      let veil = box.querySelector(':scope > .lock-veil');
      if (locked && !veil) {
        veil = document.createElement('button');
        veil.type = 'button';
        veil.className = 'lock-veil';
        veil.setAttribute('aria-label', 'Доступно после авторизации. Войти');
        veil.innerHTML = '<span class="lock-veil__ic">' + ICON_LOCK + '</span><span class="lock-veil__text">Доступно после авторизации</span>';
        veil.addEventListener('click', function () { openDialog('login', 'Материалы и PDF доступны после входа.'); });
        box.appendChild(veil);
      }
      if (!locked && veil) veil.remove();
    });
  }
  // на всякий случай: ссылки под замком не открываются, даже если до них как-то дотянуться
  document.addEventListener('click', function (e) {
    const link = e.target.closest && e.target.closest('.is-locked a');
    if (link) { e.preventDefault(); openDialog('login', 'Материалы и PDF доступны после входа.'); }
  }, true);

  // Тексты на главной про регистрацию и хранение прогресса
  function paintTexts() {
    const hero = $('heroNote');
    const note = $('progressNote');
    if (hero) hero.textContent = user
      ? 'Прогресс сохраняется в твоём аккаунте.'
      : 'Без входа — ' + GUEST_LIMIT + ' задач и калькулятор. С аккаунтом — всё остальное и прогресс на любом устройстве.';
    if (note) note.textContent = user
      ? 'Отметки о решённых задачах хранятся в твоём аккаунте: войди на любом устройстве, и прогресс будет на месте.'
      : 'Без входа отметки хранятся только в этом браузере, а решить можно ' + GUEST_LIMIT + ' задач. После регистрации они перенесутся в аккаунт и будут видны на любом устройстве.';
  }

  function paintAll() {
    paintButton();
    paintGuestNote();
    paintLocks();
    paintTexts();
  }

  /* ================= открыть и закрыть окно ================= */
  accountBtn.addEventListener('click', function () { openDialog(); });
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      setMode(tab.dataset.mode);
      showNotice('');
      emailInput.focus();
    });
  });
  dialog.querySelector('[data-auth-close]').addEventListener('click', function () { dialog.close(); });
  // клик по затемнённому фону вокруг окна тоже закрывает его
  dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });

  /* ================= при загрузке ================= */
  async function loadUser() {
    user = null;
    offline = false;
    if (getToken()) {
      try {
        const res = await api('/api/me');
        if (res.ok) user = res.data.user;
        else if (res.status === 401) writeStore(TOKEN_KEY, null); // токен устарел или вышли на другой вкладке
      } catch (e) {
        offline = true; // сервер не запущен — ограничения не включаем, чтобы не мешать вошедшему
      }
    }
    checked = true;
    if (user) {
      await pushUnsent();        // сначала досылаем то, что не успело уйти
      await pullProgress(false); // потом берём актуальный прогресс из аккаунта
    }
    paintAll();
  }

  paintAll();
  loadUser().then(function () {
    // пришли по ссылке из письма: ?confirmed=1 (почта подтверждена) или ?confirmed=0 (ссылка не сработала)
    const params = new URLSearchParams(location.search);
    // ссылка «сменить пароль»: ?reset=код — убираем код из адресной строки и открываем окно
    if (params.get('reset')) {
      history.replaceState(null, '', location.pathname + location.hash);
      showReset(params.get('reset'));
      return;
    }
    if (!params.has('confirmed')) return;
    const ok = params.get('confirmed') === '1';
    history.replaceState(null, '', location.pathname + location.hash);
    if (user) return;
    openDialog('login', ok
      ? 'Почта подтверждена! Теперь войди.'
      : 'Ссылка устарела или уже использована. Войди — если почта ещё не подтверждена, мы предложим отправить письмо снова.',
      ok ? 'ok' : 'warn');
  });

  // вошёл или вышел в другой вкладке — обновляем всё и здесь
  window.addEventListener('storage', function (e) { if (e.key === TOKEN_KEY) loadUser(); });
})();
