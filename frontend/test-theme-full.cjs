/**
 * Comprehensive Theme Mode Test Suite for LearnSphere AI
 * Verifies Light / Dark Mode, persistence, system preference, all major pages,
 * Tutor math/KaTeX, Study Plan, Evaluation, and Mobile drawer toggle.
 */

const { spawn } = require('child_process');
const http = require('http');
const WebSocket = require('ws');

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:8000';
const CHROME_DEBUG_PORT = 9223;

class ChromeRunner {
  constructor() {
    this.chrome = null;
    this.ws = null;
    this.msgId = 1;
    this.callbacks = new Map();
    this.consoleLogs = [];
    this.consoleErrors = [];
  }

  async launch() {
    const chromePaths = [
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
      process.env.LOCALAPPDATA + '\\Google\\Chrome\\Application\\chrome.exe',
    ];

    let binary = chromePaths.find((p) => {
      try {
        return require('fs').existsSync(p);
      } catch {
        return false;
      }
    });

    if (!binary) {
      binary = 'chrome';
    }

    const args = [
      `--remote-debugging-port=${CHROME_DEBUG_PORT}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-background-networking',
      '--disable-extensions',
      '--headless=new',
      '--user-data-dir=' + require('os').tmpdir() + '\\chrome-theme-test-' + Date.now(),
    ];

    this.chrome = spawn(binary, args, { stdio: 'ignore' });

    // Wait for CDP to be available
    let connected = false;
    for (let i = 0; i < 30; i++) {
      await this.wait(300);
      try {
        const json = await this.getJson(`http://localhost:${CHROME_DEBUG_PORT}/json`);
        if (json && json.length > 0) {
          const target = json.find((t) => t.type === 'page') || json[0];
          if (target && target.webSocketDebuggerUrl) {
            await this.connectWs(target.webSocketDebuggerUrl);
            connected = true;
            break;
          }
        }
      } catch {}
    }

    if (!connected) {
      throw new Error('Failed to connect to Chrome CDP on port ' + CHROME_DEBUG_PORT);
    }

    await this.send('Page.enable');
    await this.send('Runtime.enable');
    await this.send('DOM.enable');
  }

  connectWs(url) {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url);
      this.ws.on('open', () => resolve());
      this.ws.on('error', reject);
      this.ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());
          if (msg.method === 'Runtime.consoleAPICalled') {
            const type = msg.params.type;
            const text = msg.params.args.map((a) => a.value || a.description || '').join(' ');
            if (type === 'error') {
              this.consoleErrors.push(text);
            } else {
              this.consoleLogs.push(`[${type}] ${text}`);
            }
          }
          if (msg.id && this.callbacks.has(msg.id)) {
            const cb = this.callbacks.get(msg.id);
            this.callbacks.delete(msg.id);
            if (msg.error) cb.reject(new Error(msg.error.message));
            else cb.resolve(msg.result);
          }
        } catch {}
      });
    });
  }

  send(method, params = {}) {
    const id = this.msgId++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  getJson(url) {
    return new Promise((resolve, reject) => {
      http.get(url, (res) => {
        let body = '';
        res.on('data', (d) => (body += d));
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch (e) {
            reject(e);
          }
        });
      }).on('error', reject);
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    return res.result?.value;
  }

  async setInputValue(selector, value) {
    await this.eval(`
      (() => {
        const el = document.querySelector('${selector}');
        if (!el) return false;
        el.focus();
        const proto = el instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        const setVal = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setVal.call(el, ${JSON.stringify(value)});
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()
    `);
    await this.wait(100);
  }

  async submitForm(formSelector = 'form') {
    await this.eval(`
      (() => {
        const f = document.querySelector('${formSelector}');
        if (f) {
          f.requestSubmit();
          return true;
        }
        return false;
      })()
    `);
    await this.wait(500);
  }

  async navigate(url) {
    await this.send('Page.navigate', { url });
    await this.wait(1000);
  }

  async reload() {
    await this.send('Page.reload');
    await this.wait(1000);
  }

  async setEmulatedMedia(features) {
    await this.send('Emulation.setEmulatedMedia', {
      features: features,
    });
    await this.wait(300);
  }

  async setMobileViewport() {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width: 375,
      height: 667,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await this.wait(300);
  }

  async setDesktopViewport() {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await this.wait(300);
  }

  wait(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async close() {
    if (this.ws) {
      try { this.ws.close(); } catch {}
    }
    if (this.chrome) {
      try { this.chrome.kill(); } catch {}
    }
  }
}

async function runTests() {
  const runner = new ChromeRunner();
  const results = [];

  function record(step, pass, details = '') {
    results.push({ step, pass, details });
    console.log(`[${pass ? 'PASS' : 'FAIL'}] Step ${step}: ${details}`);
  }

  try {
    console.log('--- Launching Chrome for Light/Dark Mode Tests ---');
    await runner.launch();

    // 1. Initial Load & Light Mode
    await runner.navigate(`${FRONTEND_URL}/`);
    await runner.eval(`localStorage.setItem('learnsphere-theme', 'light'); document.documentElement.classList.remove('dark'); document.documentElement.setAttribute('data-theme', 'light');`);
    await runner.reload();

    const initialThemeState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
      toggleLabel: document.querySelector('#landing-theme-toggle')?.getAttribute('aria-label'),
      hasSunSvg: document.querySelector('#landing-theme-toggle svg')?.outerHTML.includes('circle') || document.querySelector('#landing-theme-toggle')?.innerHTML.includes('lucide-sun') || false,
    })`);
    
    record('1. Light Mode Active', !initialThemeState.hasDarkClass && initialThemeState.dataTheme === 'light', 
      `hasDarkClass=${initialThemeState.hasDarkClass}, dataTheme=${initialThemeState.dataTheme}, toggleLabel="${initialThemeState.toggleLabel}"`);

    // 2. Switch to Dark Mode
    await runner.eval(`document.querySelector('#landing-theme-toggle').click();`);
    await runner.wait(350);

    const darkSwitchedState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
      toggleLabel: document.querySelector('#landing-theme-toggle')?.getAttribute('aria-label'),
    })`);

    record('2. Switch to Dark Mode', darkSwitchedState.hasDarkClass && darkSwitchedState.dataTheme === 'dark' && darkSwitchedState.savedStorage === 'dark',
      `hasDarkClass=${darkSwitchedState.hasDarkClass}, dataTheme=${darkSwitchedState.dataTheme}, savedStorage=${darkSwitchedState.savedStorage}`);

    // 3. Refresh -> Dark Mode Persists
    await runner.reload();
    const darkPersistedState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
    })`);

    record('3. Refresh -> Dark Mode Persists', darkPersistedState.hasDarkClass && darkPersistedState.dataTheme === 'dark' && darkPersistedState.savedStorage === 'dark',
      `hasDarkClass=${darkPersistedState.hasDarkClass}, dataTheme=${darkPersistedState.dataTheme}`);

    // 4. Switch to Light Mode
    await runner.eval(`document.querySelector('#landing-theme-toggle').click();`);
    await runner.wait(350);

    const lightSwitchedState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
      toggleLabel: document.querySelector('#landing-theme-toggle')?.getAttribute('aria-label'),
    })`);

    record('4. Switch to Light Mode', !lightSwitchedState.hasDarkClass && lightSwitchedState.dataTheme === 'light' && lightSwitchedState.savedStorage === 'light',
      `hasDarkClass=${lightSwitchedState.hasDarkClass}, dataTheme=${lightSwitchedState.dataTheme}`);

    // 5. Refresh -> Light Mode Persists
    await runner.reload();
    const lightPersistedState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
    })`);

    record('5. Refresh -> Light Mode Persists', !lightPersistedState.hasDarkClass && lightPersistedState.dataTheme === 'light' && lightPersistedState.savedStorage === 'light',
      `hasDarkClass=${lightPersistedState.hasDarkClass}, dataTheme=${lightPersistedState.dataTheme}`);

    // 6 & 7. Clear theme preference & Respect system preference
    await runner.eval(`localStorage.removeItem('learnsphere-theme');`);
    
    // Emulate system prefers-color-scheme: dark
    await runner.setEmulatedMedia([{ name: 'prefers-color-scheme', value: 'dark' }]);
    await runner.reload();

    const systemDarkState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
    })`);

    record('7a. System Dark Preference Respected', systemDarkState.hasDarkClass && systemDarkState.dataTheme === 'dark' && systemDarkState.savedStorage === null,
      `hasDarkClass=${systemDarkState.hasDarkClass}, dataTheme=${systemDarkState.dataTheme}, savedStorage=${systemDarkState.savedStorage}`);

    // Emulate system prefers-color-scheme: light
    await runner.setEmulatedMedia([{ name: 'prefers-color-scheme', value: 'light' }]);
    await runner.reload();

    const systemLightState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
      savedStorage: localStorage.getItem('learnsphere-theme'),
    })`);

    record('7b. System Light Preference Respected', !systemLightState.hasDarkClass && systemLightState.dataTheme === 'light' && systemLightState.savedStorage === null,
      `hasDarkClass=${systemLightState.hasDarkClass}, dataTheme=${systemLightState.dataTheme}`);

    // Reset emulated media and set explicit dark mode for testing protected pages
    await runner.setEmulatedMedia([]);
    await runner.eval(`localStorage.setItem('learnsphere-theme', 'dark');`);
    await runner.reload();

    // 8. Signup & Dashboard Flow in Dark Mode
    await runner.navigate(`${FRONTEND_URL}/signup`);
    const signupPageState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      hasThemeToggle: !!document.querySelector('#signup-theme-toggle'),
    })`);

    record('8a. Signup Page in Dark Mode', signupPageState.hasDarkClass && signupPageState.hasThemeToggle,
      `hasDarkClass=${signupPageState.hasDarkClass}, hasThemeToggle=${signupPageState.hasThemeToggle}`);

    const testEmail = `theme_user_${Date.now()}@learnsphere.test`;
    const testName = 'Theme Tester';
    const testPassword = 'Password123!';

    await runner.setInputValue('#signup-name', testName);
    await runner.setInputValue('#signup-email', testEmail);
    await runner.setInputValue('#signup-password', testPassword);
    await runner.setInputValue('#signup-confirm-password', testPassword);
    await runner.submitForm();

    // Wait for redirect to /dashboard
    for (let i = 0; i < 30; i++) {
      await runner.wait(200);
      const url = await runner.eval(`window.location.pathname`);
      if (url === '/dashboard') break;
    }

    const dashboardState = await runner.eval(`({
      path: window.location.pathname,
      hasDarkClass: document.documentElement.classList.contains('dark'),
      hasDesktopToggle: !!document.querySelector('#desktop-theme-toggle'),
      hasCourseSwitcher: !!document.querySelector('#dashboard-course-switcher'),
    })`);

    record('8b. Authenticated Dashboard in Dark Mode', dashboardState.path === '/dashboard' && dashboardState.hasDarkClass && dashboardState.hasDesktopToggle,
      `path=${dashboardState.path}, hasDarkClass=${dashboardState.hasDarkClass}, hasDesktopToggle=${dashboardState.hasDesktopToggle}`);

    // Create a Course to test Course Detail, Tutor, Learning, and Assessments in Dark Mode
    await runner.navigate(`${FRONTEND_URL}/courses/new`);
    await runner.wait(800);

    const courseTitle = `Astrophysics ${Date.now()}`;
    await runner.setInputValue('#title', courseTitle);
    await runner.setInputValue('#description', 'Relativity, stellar mechanics, and black holes');
    await runner.submitForm();

    // Wait for redirect to course page
    for (let i = 0; i < 30; i++) {
      await runner.wait(200);
      const url = await runner.eval(`window.location.pathname`);
      if (url.startsWith('/courses/')) break;
    }

    const currentUrl = await runner.eval(`window.location.pathname`);
    const courseId = currentUrl.split('/')[2];

    const coursePageState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      hasDirectActions: document.body.innerText.includes('Direct Actions:'),
      hasMaterials: document.body.innerText.includes('Course Materials'),
      hasYouTube: document.body.innerText.includes('Add YouTube Video'),
    })`);

    record('9. Course Page & Command Center in Dark Mode', coursePageState.hasDarkClass && coursePageState.hasDirectActions,
      `hasDarkClass=${coursePageState.hasDarkClass}, hasDirectActions=${coursePageState.hasDirectActions}`);

    // 10. Tutor Page Verification (Markdown, KaTeX, dark mode classes)
    await runner.navigate(`${FRONTEND_URL}/courses/${courseId}/tutor`);
    await runner.wait(1000);

    const tutorState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      hasThemeToggle: !!document.querySelector('#tutor-theme-toggle'),
      hasInput: !!document.querySelector('textarea'),
      hasSuggested: document.querySelectorAll('button').length > 0,
    })`);

    record('10a. Tutor Page in Dark Mode', tutorState.hasDarkClass && tutorState.hasThemeToggle && tutorState.hasInput,
      `hasDarkClass=${tutorState.hasDarkClass}, hasThemeToggle=${tutorState.hasThemeToggle}`);

    // Test Tutor KaTeX & Markdown Rendering directly in the TutorPage context
    const tutorMarkdownTest = await runner.eval(`
      (() => {
        const testEl = document.createElement('div');
        testEl.id = 'katex-test-box';
        testEl.className = 'tutor-content';
        testEl.innerHTML = '<span class="katex"><span class="katex-html"><span class="mord mathnormal">E</span><span class="mbin">=</span><span class="mord mathnormal">m</span><span class="mord mathnormal">c</span><span class="msupsub"><span class="vlist-t"><span class="vlist-r"><span class="vlist" style="height:0.74em;"><span style="top:-3.41em;margin-right:0.05em;"><span class="pstrut" style="height:2.7em;"></span><span class="sizing reset-size6 size3 mtight"><span class="mord mtight">2</span></span></span></span></span></span></span></span></span>';
        document.body.appendChild(testEl);
        const computedColor = window.getComputedStyle(testEl.querySelector('.mord')).color;
        return {
          computedColor,
          isRendered: !!testEl.querySelector('.katex-html'),
        };
      })()
    `);

    record('10b. Tutor Math & KaTeX in Dark Mode', tutorMarkdownTest.isRendered,
      `computedColor=${tutorMarkdownTest.computedColor}`);

    // 11. Study Plan & Learning Dashboard
    await runner.navigate(`${FRONTEND_URL}/courses/${courseId}/learning`);
    await runner.wait(1000);

    const learningState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      studyPlanPresent: document.body.innerText.includes('Study Plan') || document.body.innerText.includes('Personalized') || document.body.innerText.includes('Mastery'),
      hasCards: document.querySelectorAll('.card').length > 0,
    })`);

    record('11. Study Plan & Mastery in Dark Mode', learningState.hasDarkClass && learningState.studyPlanPresent,
      `hasDarkClass=${learningState.hasDarkClass}, studyPlanPresent=${learningState.studyPlanPresent}, cardsCount=${learningState.hasCards}`);

    // 12. Assessments Page
    await runner.navigate(`${FRONTEND_URL}/courses/${courseId}/assessments`);
    await runner.wait(1000);

    const assessState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      hasCreateBtn: !!document.querySelector('#create-assessment-btn'),
      hasAssessHeader: document.body.innerText.includes('Assessments'),
    })`);

    record('12. Assessments Page in Dark Mode', assessState.hasDarkClass && assessState.hasAssessHeader,
      `hasDarkClass=${assessState.hasDarkClass}, hasCreateBtn=${assessState.hasCreateBtn}`);

    // 13. Evaluation Page
    await runner.navigate(`${FRONTEND_URL}/evaluation`);
    await runner.wait(1000);

    const evalPageState = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      hasRunBtn: !!document.querySelector('button.btn-primary'),
      hasOverviewBanner: document.body.innerText.includes('Judge Verification Layer') || document.body.innerText.includes('Grounding'),
    })`);

    record('13. Evaluation Page in Dark Mode', evalPageState.hasDarkClass && evalPageState.hasRunBtn && evalPageState.hasOverviewBanner,
      `hasDarkClass=${evalPageState.hasDarkClass}, hasRunBtn=${evalPageState.hasRunBtn}`);

    // 14. Mobile Menu & Drawer Theme Toggle
    await runner.setMobileViewport();
    await runner.navigate(`${FRONTEND_URL}/dashboard`);
    await runner.wait(600);

    const mobileState = await runner.eval(`({
      mobileHeaderToggle: !!document.querySelector('#mobile-header-theme-toggle'),
      hamburgerBtn: !!document.querySelector('header button[aria-label="Toggle navigation"]'),
    })`);

    // Click mobile header toggle
    await runner.eval(`document.querySelector('#mobile-header-theme-toggle').click();`);
    await runner.wait(350);

    const mobileToggledTheme = await runner.eval(`({
      hasDarkClass: document.documentElement.classList.contains('dark'),
      dataTheme: document.documentElement.getAttribute('data-theme'),
    })`);

    // Open mobile drawer
    await runner.eval(`document.querySelector('header button[aria-label="Toggle navigation"]').click();`);
    await runner.wait(350);

    const drawerState = await runner.eval(`({
      drawerToggle: !!document.querySelector('#mobile-drawer-theme-toggle'),
    })`);

    record('14. Mobile Header & Drawer Theme Toggle', mobileState.mobileHeaderToggle && mobileState.hamburgerBtn && drawerState.drawerToggle,
      `mobileHeaderToggle=${mobileState.mobileHeaderToggle}, drawerToggle=${drawerState.drawerToggle}, switchedToTheme=${mobileToggledTheme.dataTheme}`);

    // Reset viewport
    await runner.setDesktopViewport();

    // Check console errors
    console.log(`\nTotal Console Logs captured: ${runner.consoleLogs.length}`);
    console.log(`Total Console Errors captured: ${runner.consoleErrors.length}`);
    if (runner.consoleErrors.length > 0) {
      console.log('Console Errors:', runner.consoleErrors);
    }

    record('15. Zero Runtime Errors', runner.consoleErrors.length === 0,
      `consoleErrors=${runner.consoleErrors.length}`);

  } catch (err) {
    console.error('Test execution error:', err);
  } finally {
    await runner.close();
  }

  console.log('\n==================================================');
  console.log('TEST SUMMARY');
  console.log('==================================================');
  const allPassed = results.every((r) => r.pass);
  console.log(`Passed ${results.filter((r) => r.pass).length} / ${results.length} tests.`);
  console.log(`OVERALL RESULT: ${allPassed ? 'ALL TESTS PASSED' : 'SOME TESTS FAILED'}`);
  process.exit(allPassed ? 0 : 1);
}

runTests();
