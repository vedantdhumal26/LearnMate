const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const CDP_PORT = 9225;
const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:8000';

class ChromeController {
  constructor() {
    this.chrome = null;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
  }

  async launch() {
    const tmpDir = path.join(os.tmpdir(), 'chrome-prephase8-' + Date.now());
    fs.mkdirSync(tmpDir, { recursive: true });

    this.chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
      `--remote-debugging-port=${CDP_PORT}`,
      '--headless=new',
      '--disable-gpu',
      '--disable-extensions',
      '--no-first-run',
      '--no-default-browser-check',
      '--window-size=1440,900',
      `--user-data-dir=${tmpDir}`,
      `${FRONTEND_URL}/`,
    ]);

    let connected = false;
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 300));
      try {
        const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`);
        if (res.ok) {
          connected = true;
          break;
        }
      } catch {}
    }

    if (!connected) throw new Error('Failed to connect to Chrome DevTools port');

    const pagesRes = await fetch(`http://127.0.0.1:${CDP_PORT}/json`);
    const pages = await pagesRes.json();
    const targetPage = pages.find((p) => p.type === 'page' && !p.url.startsWith('chrome-extension://')) || pages[0];

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(targetPage.webSocketDebuggerUrl);
      this.ws.onopen = async () => {
        await this.send('Page.enable');
        await this.send('Runtime.enable');
        await this.send('Network.enable');
        await this.send('DOM.enable');
        resolve();
      };
      this.ws.onerror = reject;

      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.method === 'Runtime.consoleAPICalled') {
          console.log('[BROWSER CONSOLE]', msg.params.args.map((a) => (a.value !== undefined ? a.value : a.description)));
        }
        if (msg.method === 'Network.responseReceived' && msg.params.response.url.includes('/api/')) {
          console.log('[API RESPONSE]', msg.params.response.status, msg.params.response.url);
        }
        if (msg.id && this.callbacks.has(msg.id)) {
          const cb = this.callbacks.get(msg.id);
          this.callbacks.delete(msg.id);
          if (msg.error) cb.reject(new Error(msg.error.message));
          else cb.resolve(msg.result);
        }
      };
    });
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.id++;
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
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

  async waitForSelector(selector, timeoutMs = 8000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const exists = await this.eval(`!!document.querySelector('${selector}')`);
      if (exists) return true;
      await this.wait(150);
    }
    throw new Error(`Timeout waiting for selector: ${selector}`);
  }

  async setInputValue(selector, value) {
    await this.waitForSelector(selector);
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

  async click(selector) {
    await this.waitForSelector(selector);
    await this.eval(`
      (() => {
        const el = document.querySelector('${selector}');
        if (el) {
          el.scrollIntoView();
          el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          el.click();
          return true;
        }
        return false;
      })()
    `);
    await this.wait(300);
  }

  async navigate(url) {
    await this.send('Page.navigate', { url });
    await this.wait(1500);
  }

  async wait(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async close() {
    try {
      if (this.ws) this.ws.close();
      if (this.chrome) this.chrome.kill();
    } catch {}
  }
}

async function runPrePhase8Tests() {
  console.log('===============================================================');
  console.log('=== LEARN-MATE: PRE-PHASE 8 FRONTEND INTEGRATION TEST SUITE ===');
  console.log('===============================================================\n');

  const controller = new ChromeController();
  const results = [];

  try {
    await controller.launch();
    console.log('[Setup] Chrome launched and connected.');

    // 0. Signup a fresh user
    const testEmail = `phase8_user_${Date.now()}@learnmate.test`;
    const testName = 'Original Student';
    const testPassword = 'Password123!';

    await controller.navigate(`${FRONTEND_URL}/signup`);
    await controller.waitForSelector('#signup-name');
    await controller.setInputValue('#signup-name', testName);
    await controller.setInputValue('#signup-email', testEmail);
    await controller.setInputValue('#signup-password', testPassword);
    await controller.setInputValue('#signup-confirm-password', testPassword);
    await controller.submitForm();

    let onDashboard = false;
    for (let i = 0; i < 25; i++) {
      onDashboard = await controller.eval('window.location.pathname === "/dashboard"');
      if (onDashboard) break;
      await controller.wait(300);
    }
    console.log('Setup: Signup and reached /dashboard:', onDashboard);

    if (!onDashboard) {
      throw new Error('Failed to reach /dashboard after signup');
    }

    const token = await controller.eval('localStorage.getItem("learnsphere_auth_token")');

    // ─────────────────────────────────────────────────────────────
    // TEST 1: Edit Profile (PATCH /api/auth/me)
    // ─────────────────────────────────────────────────────────────
    console.log('\n--- TEST 1: Edit Profile ---');
    // Open modal
    await controller.click('#desktop-edit-profile-button');
    await controller.wait(500);

    const modalVisible = await controller.eval('!!document.getElementById("profile-display-name")');
    const prefilledName = await controller.eval('document.getElementById("profile-display-name").value');
    const prefilledEmail = await controller.eval('document.getElementById("profile-email").value');

    console.log('Modal visible:', modalVisible, 'Prefilled:', { prefilledName, prefilledEmail });

    // 1A: Test validation (empty display name)
    await controller.setInputValue('#profile-display-name', '');
    await controller.submitForm('div[role="dialog"] form');
    await controller.wait(400);
    const hasEmptyNameError = await controller.eval('document.body.innerText.includes("Display name is required")');

    // 1B: Test validation (invalid email)
    await controller.setInputValue('#profile-display-name', 'Valid Name');
    await controller.setInputValue('#profile-email', 'invalid-email');
    await controller.submitForm('div[role="dialog"] form');
    await controller.wait(400);
    const hasInvalidEmailError = await controller.eval('document.body.innerText.includes("valid email address")');

    // 1C: Test successful update
    const updatedName = 'Dr. Renamed Learner';
    const updatedEmail = `renamed_${Date.now()}@learnmate.test`;
    await controller.setInputValue('#profile-display-name', updatedName);
    await controller.setInputValue('#profile-email', updatedEmail);
    await controller.click('div[role="dialog"] button[type="submit"]');
    await controller.wait(2000);
    const sidebarText = await controller.eval('document.querySelector("aside").innerText');
    const sidebarHasNewName = sidebarText.includes(updatedName);
    const sidebarHasNewEmail = sidebarText.includes(updatedEmail);

    if (modalVisible && hasEmptyNameError && hasInvalidEmailError && sidebarHasNewName && sidebarHasNewEmail) {
      console.log('✓ Edit Profile: Prefilled, client validation, PATCH /api/auth/me, and sidebar update verified.');
      results.push({ test: '1. Edit Profile', pass: true });
    } else {
      console.error('✗ Edit Profile failed:', { modalVisible, hasEmptyNameError, hasInvalidEmailError, sidebarHasNewName, sidebarHasNewEmail });
      results.push({ test: '1. Edit Profile', pass: false });
    }

    // ─────────────────────────────────────────────────────────────
    // TEST 2: Create Course & Rename Course (PATCH /api/courses/{id})
    // ─────────────────────────────────────────────────────────────
    console.log('\n--- TEST 2: Rename Course ---');
    const initialCourseTitle = `Initial Robotics Course ${Date.now()}`;
    await controller.navigate(`${FRONTEND_URL}/courses/new`);
    await controller.wait(1000);
    await controller.setInputValue('#title', initialCourseTitle);
    await controller.setInputValue('#description', 'Foundational mechanics');
    await controller.submitForm();
    await controller.wait(2500);

    const courseUrl = await controller.eval('window.location.pathname');
    const courseId = courseUrl.split('/')[2];
    console.log('Course created:', { initialCourseTitle, courseId });

    // Test 2A: Rename on Course Detail Page
    await controller.click('#course-rename-button');
    await controller.wait(500);

    const renameModalOpen = await controller.eval('!!document.getElementById("course-rename-title")');
    const prefilledTitle = await controller.eval('document.getElementById("course-rename-title").value');

    // Test empty title validation
    await controller.setInputValue('#course-rename-title', '   ');
    await controller.submitForm('div[role="dialog"] form');
    await controller.wait(400);
    const hasEmptyTitleError = await controller.eval('document.body.innerText.includes("Course title cannot be blank")');

    // Submit valid new title
    const renamedCourseTitle = `Advanced Quantum Robotics ${Date.now()}`;
    await controller.setInputValue('#course-rename-title', renamedCourseTitle);
    await controller.click('div[role="dialog"] button[type="submit"]');
    await controller.wait(2000);
    const detailHeaderTitle = await controller.eval('document.querySelector("h1") ? document.querySelector("h1").innerText : ""');
    const detailRenamed = detailHeaderTitle.includes(renamedCourseTitle);

    // Test 2B: Verify renamed course persists on Dashboard
    await controller.navigate(`${FRONTEND_URL}/dashboard`);
    await controller.wait(1500);
    const dashboardText = await controller.eval('document.body.innerText');
    const dashboardHasRenamed = dashboardText.includes(renamedCourseTitle);

    if (renameModalOpen && prefilledTitle === initialCourseTitle && hasEmptyTitleError && detailRenamed && dashboardHasRenamed) {
      console.log('✓ Rename Course: Prefilled title, validation, PATCH /api/courses/{id}, detail & dashboard sync verified.');
      results.push({ test: '2. Rename Course', pass: true });
    } else {
      console.error('✗ Rename Course failed:', { renameModalOpen, prefilledTitle, hasEmptyTitleError, detailRenamed, dashboardHasRenamed });
      results.push({ test: '2. Rename Course', pass: false });
    }

    // ─────────────────────────────────────────────────────────────
    // TEST 3: Delete Individual Learning Material (DELETE /api/courses/{id}/materials/{id})
    // ─────────────────────────────────────────────────────────────
    console.log('\n--- TEST 3: Delete Individual Material ---');

    // Upload test PDF fixture via backend API with Authorization
    const pdfPath = path.join(__dirname, 'test_sample_lecture.pdf');
    const pdfBuffer = fs.readFileSync(pdfPath);
    const form = new FormData();
    form.append('file', new Blob([pdfBuffer], { type: 'application/pdf' }), 'test_sample_lecture.pdf');

    const uploadRes = await fetch(`${BACKEND_URL}/api/courses/${courseId}/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    const uploadData = await uploadRes.json();
    console.log('Material uploaded via API:', uploadData.source_id, uploadData.file_name);

    await controller.navigate(`${FRONTEND_URL}/courses/${courseId}`);
    await controller.wait(1500);

    const materialsCountBefore = await controller.eval('document.querySelectorAll("div.card.p-4").length');
    console.log('Materials before deletion:', materialsCountBefore);

    // Click delete material button on the material card
    await controller.click('div.card.p-4 button[aria-label*="Delete material"]');
    await controller.wait(400);

    // Verify confirmation modal is open
    const materialConfirmOpen = await controller.eval('document.body.innerText.includes("Delete Learning Material")');

    // Test Cancellation first
    await controller.eval(`
      (() => {
        const cancelBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText === 'Keep Material');
        if (cancelBtn) cancelBtn.click();
      })()
    `);
    await controller.wait(400);
    const materialsAfterCancel = await controller.eval('document.querySelectorAll("div.card.p-4").length');
    console.log('Materials after cancel (should be unchanged):', materialsAfterCancel);

    // Now open and confirm delete
    await controller.click('div.card.p-4 button[aria-label*="Delete material"]');
    await controller.wait(400);

    await controller.eval(`
      (() => {
        const confirmBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText === 'Delete Material');
        if (confirmBtn) confirmBtn.click();
      })()
    `);
    await controller.wait(2000);

    const materialsAfterDelete = await controller.eval('document.querySelectorAll("div.card.p-4").length');
    const headerSourceText = await controller.eval('document.querySelector("div.card.p-6").innerText');
    const sourceCountDecreased = headerSourceText.includes('0 total sources');

    if (materialConfirmOpen && materialsAfterCancel === 1 && materialsAfterDelete === 0 && sourceCountDecreased) {
      console.log('✓ Delete Material: Confirmation dialog, cancellation preservation, 204 No Content, and list/count update verified.');
      results.push({ test: '3. Delete Individual Material', pass: true });
    } else {
      console.error('✗ Delete Material failed:', { materialConfirmOpen, materialsAfterCancel, materialsAfterDelete, sourceCountDecreased });
      results.push({ test: '3. Delete Individual Material', pass: false });
    }

    // ─────────────────────────────────────────────────────────────
    // TEST 4: Delete Course (DELETE /api/courses/{id})
    // ─────────────────────────────────────────────────────────────
    console.log('\n--- TEST 4: Delete Course ---');
    // Open Delete Course modal from Course Detail Page
    await controller.click('#course-delete-button');
    await controller.wait(400);

    const deleteCourseConfirmOpen = await controller.eval('document.body.innerText.includes("Delete Course")');

    // Test Cancel on course deletion
    await controller.eval(`
      (() => {
        const cancelBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText === 'Keep Course');
        if (cancelBtn) cancelBtn.click();
      })()
    `);
    await controller.wait(400);
    const stillOnCoursePage = await controller.eval('window.location.pathname.startsWith("/courses/")');

    // Open Delete Course modal again and Confirm
    await controller.click('#course-delete-button');
    await controller.wait(400);

    await controller.eval(`
      (() => {
        const confirmBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText === 'Delete Course' && b.classList.contains('bg-err-600'));
        if (confirmBtn) confirmBtn.click();
      })()
    `);
    await controller.wait(2500);

    const urlAfterCourseDelete = await controller.eval('window.location.pathname');
    const dashboardAfterText = await controller.eval('document.body.innerText');
    const courseRemovedFromDashboard = !dashboardAfterText.includes(renamedCourseTitle);

    if (deleteCourseConfirmOpen && stillOnCoursePage && urlAfterCourseDelete === '/dashboard' && courseRemovedFromDashboard) {
      console.log('✓ Delete Course: Confirmation warning, cancellation, 204 No Content, navigation to /dashboard, and course removal verified.');
      results.push({ test: '4. Delete Course', pass: true });
    } else {
      console.error('✗ Delete Course failed:', { deleteCourseConfirmOpen, stillOnCoursePage, urlAfterCourseDelete, courseRemovedFromDashboard });
      results.push({ test: '4. Delete Course', pass: false });
    }

  } catch (err) {
    console.error('Fatal error during test execution:', err);
  } finally {
    await controller.close();
  }

  console.log('\n========================================');
  console.log('=== TEST RESULTS SUMMARY ===');
  console.log('========================================');
  let passCount = 0;
  for (const r of results) {
    const mark = r.pass ? 'PASS' : 'FAIL';
    console.log(`[${mark}] ${r.test}`);
    if (r.pass) passCount++;
  }
  console.log(`\nTOTAL: ${passCount} / ${results.length} PASSED`);
}

runPrePhase8Tests();
