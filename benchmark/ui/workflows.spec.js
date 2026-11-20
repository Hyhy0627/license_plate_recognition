const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a11sAAAAASUVORK5CYII=', 'base64');
const image = { name: 'plate.png', mimeType: 'image/png', buffer: png };
const video = { name: 'clip.mp4', mimeType: 'video/mp4', buffer: Buffer.from('controlled-invalid-video') };
function mixedVideoResult() {
  const tracks = [
    { track_id: 1, plate_number: '30A-123.45', plate_status: 'tentative' },
    { track_id: 2, plate_number: '51B-053.49', plate_status: 'needs_review', plate_candidates: ['51B-053.49', '51B-053.48'] },
    { track_id: 3, plate_number: null, plate_status: 'unreadable' },
  ].map(track => ({ vehicle_type: 'Ô tô', first_seen: 0, last_seen: 1, ...track }));
  // The unreadable box overlaps the first plate, so it would also intercept its hover.
  const boxes = [[120, 100, 220, 250], [240, 100, 340, 250], [150, 145, 190, 205]];
  const vehicles = tracks.map(({ track_id, vehicle_type }, i) => ({ track_id, vehicle_type, bbox: boxes[i] }));
  return { duration: 1, fps: 30, sample_fps: 5, frame_width: 640, frame_height: 360,
    mode: 'fast', processing_seconds: .1, tracks, frames: [{ time: 0, vehicles }] };
}
const runtimeErrors = new WeakMap();
test.beforeEach(async ({ page }) => {
  const errors = []; runtimeErrors.set(page, errors);
  page.on('pageerror', error => errors.push(error.message));
});
test.afterEach(async ({ page }) => {
  const errors = runtimeErrors.get(page) || [];
  if (errors.length) await test.info().attach('runtime-warnings', { body: JSON.stringify(errors, null, 2), contentType: 'application/json' });
});

// Every API/static request is intercepted: these tests never write the user's database.
async function backend(page, authenticated = true) {
  const state = { authenticated, imageCalls: 0, videoCalls: 0, imageError: false, videoFailure: false, historyError: false, polls: 0, videoResult: mixedVideoResult() };
  const user = { id: 1, name: 'Benchmark User', email: 'benchmark@example.com' };
  const records = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, plate_number: `30A-${String(12345 + i).slice(0, 3)}.${String(12345 + i).slice(3)}`,
    confidence: .95, plate_type: 'one_line', created_at: '2026-11-19 10:00:00', cropped_plate_url: '/static/cropped_plates/test.png' }));
  for (const path of ['cropped_plates', 'final_results']) {
    await page.route(`**/static/${path}/**`, route => route.fulfill({ body: png, contentType: 'image/png', headers: { 'access-control-allow-origin': '*' } }));
  }
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url()), p = url.pathname;
    const reply = (body, status = 200) => route.fulfill({ status, json: body,
      headers: { 'access-control-allow-origin': 'http://127.0.0.1:13000', 'access-control-allow-credentials': 'true',
        'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'GET,POST,OPTIONS' } });
    if (request.method() === 'OPTIONS') return reply({});
    if (p === '/api/auth/me') {
      await new Promise(resolve => setTimeout(resolve, 80));
      return reply(state.authenticated ? { user } : { detail: 'Chưa đăng nhập' }, state.authenticated ? 200 : 401);
    }
    if (p.endsWith('/logout')) { state.authenticated = false; return reply({ success: true }); }
    if (p.endsWith('/register') || p.endsWith('/login')) {
      if (request.postDataJSON().password === 'Wrong password') return reply({ detail: 'Email hoặc mật khẩu không đúng.' }, 401);
      state.authenticated = true; return reply({ user }, p.endsWith('/register') ? 201 : 200);
    }
    if (p.endsWith('/detect')) {
      state.imageCalls++;
      if (state.imageError) return reply({ detail: 'Không xử lý được ảnh thử nghiệm.' }, 500);
      return reply({ success: true, total_detected: 2, processing_time_ms: 123, cloud_attempts: 0, warnings: [],
        results: ['30A-123.45', '51B-053.49'].map(plate_number => ({ plate_number, confidence: .95, plate_type: 'one_line', bbox: [0, 0, 1, 1],
          is_valid_format: true, engine_used: 'local_yolo', cropped_image_url: '/static/cropped_plates/test.png', annotated_image_url: '/static/final_results/test.png' })) });
    }
    if (p.includes('/license-plates/history') || p.includes('/license-plates/search')) {
      if (state.historyError) return reply({ detail: 'history error' }, 500);
      const query = (url.searchParams.get('plate') || '').replace(/[^a-z0-9]/gi, '').toUpperCase();
      const matched = records.filter(r => r.plate_number.replace(/[^a-z0-9]/gi, '').includes(query));
      const current = Number(url.searchParams.get('page') || 1);
      return reply({ total: matched.length, page: current, page_size: 20, items: matched.slice((current - 1) * 20, current * 20), results: matched.slice((current - 1) * 20, current * 20) });
    }
    if (p.endsWith('/jobs') && request.method() === 'POST') {
      state.videoCalls++; state.polls = 0;
      return reply({ id: 'controlled-job', status: 'queued', progress: 0 }, 202);
    }
    if (p.endsWith('/media')) return route.fulfill({ body: video.buffer, contentType: 'video/mp4' });
    if (p.includes('/jobs/')) {
      state.polls++;
      if (state.videoFailure) return reply({ id: 'controlled-job', status: 'failed', progress: 0, error: 'Không đọc được video thử nghiệm.' });
      if (state.polls === 1) return reply({ id: 'controlled-job', status: 'running', progress: 50 });
      return reply({ id: 'controlled-job', status: 'completed', progress: 100, result: state.videoResult });
    }
    return reply({ detail: `Unimplemented mock: ${p}` }, 501);
  });
  return state;
}

for (const target of ['/', '/history', '/video']) {
  test(`guest redirects from ${target}`, async ({ page }) => {
    await backend(page, false); await page.goto(target);
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  });
}

test('register validation, password visibility, submit, reload, logout and login', async ({ page }) => {
  await backend(page, false); await page.goto('/register');
  await page.getByLabel('Họ và tên').fill('Benchmark User');
  await page.getByLabel('Email', { exact: true }).fill('benchmark@example.com');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Benchmark phrase 2026');
  await page.getByLabel('Nhập lại mật khẩu', { exact: true }).fill('Mismatch password');
  await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'chưa khớp' })).toBeVisible();
  await page.getByRole('button', { name: 'Hiện mật khẩu', exact: true }).click();
  await expect(page.getByLabel('Mật khẩu', { exact: true })).toHaveAttribute('type', 'text');
  await page.getByLabel('Nhập lại mật khẩu', { exact: true }).fill('Benchmark phrase 2026');
  await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
  await expect(page).toHaveURL('http://127.0.0.1:13000/');
  await page.reload(); await page.getByRole('button', { name: 'Đăng xuất', exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.waitForLoadState('networkidle');
  await page.getByLabel('Email', { exact: true }).fill('benchmark@example.com');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Wrong password');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'không đúng' })).toBeVisible();
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Benchmark phrase 2026');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await expect(page).toHaveURL('http://127.0.0.1:13000/');
});

test('image auto upload, multiple plates, annotation toggle, replace and clear', async ({ page }) => {
  const state = await backend(page); await page.goto('/');
  await page.getByLabel('Chọn ảnh phương tiện').setInputFiles(image);
  await expect(page.getByRole('button', { name: 'Biển 02' })).toBeVisible();
  expect(state.imageCalls).toBe(1);
  await page.getByRole('button', { name: 'Biển 02' }).click();
  await expect(page.getByRole('button', { name: 'Biển 02' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Đang hiện vùng nhận diện' }).click();
  await expect(page.getByRole('button', { name: 'Đang xem ảnh gốc' })).toBeVisible();
  await page.getByLabel('Chọn ảnh phương tiện').setInputFiles({ ...image, name: 'second.png' });
  await expect.poll(() => state.imageCalls).toBe(2);
  await page.getByRole('button', { name: 'Xóa ảnh và bắt đầu lại' }).click();
  await expect(page.getByRole('button', { name: /Chọn hình ảnh/ })).toBeVisible();
});

test('image validation and backend failure are visible', async ({ page }) => {
  const state = await backend(page); await page.goto('/');
  await page.getByLabel('Chọn ảnh phương tiện').setInputFiles({ name: 'bad.txt', mimeType: 'text/plain', buffer: Buffer.from('bad') });
  await expect(page.getByRole('alert').filter({ hasText: 'JPG, PNG hoặc WEBP' })).toBeVisible();
  expect(state.imageCalls).toBe(0);
  state.imageError = true;
  await page.getByLabel('Chọn ảnh phương tiện').setInputFiles(image);
  await expect(page.getByRole('alert').filter({ hasText: 'Không xử lý được ảnh thử nghiệm' })).toBeVisible();
  state.imageError = false;
  await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Biển 02' })).toBeVisible();
  await page.getByLabel('Chọn ảnh phương tiện').setInputFiles({ ...image, buffer: Buffer.alloc(10 * 1024 * 1024 + 1) });
  await expect(page.getByRole('alert').filter({ hasText: '10 MB' })).toBeVisible();
});

test('history pagination, search, clear and refresh', async ({ page }) => {
  await backend(page); await page.goto('/history');
  await expect(page.getByText('Trang 1 / 2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Trang sau' }).click();
  await expect(page.getByText('Trang 2 / 2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Trang trước' }).click();
  await page.getByPlaceholder('Nhập biển số cần tìm...').fill('99Z99999');
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.getByText(/Không tìm thấy kết quả cho/)).toBeVisible();
  await page.getByRole('button', { name: 'Xóa tìm kiếm' }).click();
  await expect(page.getByText('Trang 1 / 2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Tải lại lịch sử' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(20);
});

test('history network failure', async ({ page }) => {
  const state = await backend(page); state.historyError = true; await page.goto('/history');
  await expect(page.getByRole('alert').filter({ hasText: '500' })).toBeVisible();
});

test('video auto analysis runs once, polls, selects one label and reruns', async ({ page }) => {
  const state = await backend(page); await page.goto('/video');
  await page.getByLabel('Chọn video giao thông').setInputFiles(video);
  await expect(page.getByText(/Hoàn tất phân tích trong/)).toBeVisible();
  expect(state.videoCalls).toBe(1);
  expect(state.polls).toBeGreaterThanOrEqual(2);
  await expect(page.locator('.video-stats strong').first()).toHaveText('2');
  await expect(page.locator('.video-track')).toHaveCount(2);
  await expect(page.getByRole('button', { name: /#1 30A-123.45/ })).toContainText('Cần đối chiếu hình ảnh');
  await expect(page.getByRole('button', { name: /#2 51B-053.49/ })).toContainText('Các lượt đọc khác nhau');
  await expect(page.locator('.vehicle-box')).toHaveCount(2);
  await expect(page.locator('.vehicle-box > span')).toHaveCount(0);
  const box = await page.locator('.vehicle-box').first().boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.locator('.vehicle-box > span')).toHaveText('30A-123.45');
  await page.mouse.move(0, 0);
  await expect(page.locator('.vehicle-box > span')).toHaveCount(0);
  await page.getByRole('button', { name: /#1 30A-123.45/ }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.vehicle-box > span')).toHaveText('30A-123.45');
  await test.info().attach('selected-video', { body: await page.screenshot(), contentType: 'image/png' });
  await expect(page.locator('video')).toHaveAttribute('controls', '');
  await page.getByRole('button', { name: 'Phân tích lại', exact: true }).click();
  await expect.poll(() => state.videoCalls).toBe(2);
  await expect(page.getByText(/Hoàn tất phân tích trong/)).toBeVisible();
});

test('video with only unreadable plates has no rows or boxes', async ({ page }) => {
  const state = await backend(page);
  state.videoResult.tracks.forEach((track, i) => {
    track.plate_number = [null, '', '   '][i];
    track.plate_status = 'unreadable';
  });
  await page.goto('/video');
  await page.getByLabel('Chọn video giao thông').setInputFiles(video);
  await expect(page.getByText(/Chưa đọc được biển số nào trong video này/)).toBeVisible();
  await expect(page.locator('.video-stats strong').first()).toHaveText('0');
  await expect(page.locator('.video-track')).toHaveCount(0);
  await expect(page.locator('.vehicle-box')).toHaveCount(0);
});

test('video replay of 59-V1 shows only its plate on a mixed frame', async ({ page }) => {
  const samples = path.resolve(__dirname, '../../data/benchmarks');
  const clip = path.join(samples, 'video_samples/bien_so_ro_59V1_84625.webm');
  const savedResult = path.join(samples, 'video_fix/api_result.json');
  test.skip(!fs.existsSync(clip) || !fs.existsSync(savedResult), 'Local benchmark recording and saved result required');
  const state = await backend(page);
  state.videoResult = JSON.parse(fs.readFileSync(savedResult, 'utf8'));
  await page.route('**/jobs/controlled-job/media', route => route.fulfill({
    path: clip, contentType: 'video/webm',
    headers: { 'access-control-allow-origin': 'http://127.0.0.1:13000', 'access-control-allow-credentials': 'true' },
  }));
  await page.goto('/video');
  await page.getByLabel('Chọn video giao thông').setInputFiles(clip);
  const row = page.getByRole('button', { name: /#2 59-V1 846\.25/ });
  await expect(page.locator('.video-track')).toHaveCount(1);
  await expect(page.locator('.video-stats strong').first()).toHaveText('1');
  await row.click();
  const box = page.locator('.vehicle-box');
  await expect(box.locator('span')).toHaveText('59-V1 846.25');
  const player = page.locator('video');
  await player.evaluate(video => video.play());
  await expect.poll(() => player.evaluate(video => video.currentTime)).toBeGreaterThanOrEqual(0.4);
  const time = await player.evaluate(video => { video.pause(); return video.currentTime; });
  const frame = state.videoResult.frames.reduce((closest, sample) =>
    Math.abs(sample.time - time) < Math.abs(closest.time - time) ? sample : closest);
  expect(frame.vehicles.map(vehicle => vehicle.track_id).sort()).toEqual([1, 2]);
  const plate = frame.vehicles.find(vehicle => vehicle.track_id === 2);
  const expectedLeft = plate.bbox[0] / state.videoResult.frame_width * 100;
  await expect(box).toHaveCount(1);
  await expect.poll(() => box.evaluate(element => parseFloat(element.style.left))).toBeCloseTo(expectedLeft, 3);
  await expect(box.locator('span')).toHaveText('59-V1 846.25');
  await test.info().attach('video-59V1', { body: await page.screenshot(), contentType: 'image/png' });
});

for (const mode of ['paste', 'drop']) {
  test(`image ${mode} starts recognition`, async ({ page }) => {
    const state = await backend(page); await page.goto('/');
    await expect(page.getByLabel('Chọn ảnh phương tiện')).toBeAttached();
    await page.evaluate(({ mode, bytes }) => {
      const transfer = new DataTransfer();
      transfer.items.add(new File([new Uint8Array(bytes)], 'plate.png', { type: 'image/png' }));
      if (mode === 'paste') window.dispatchEvent(new ClipboardEvent('paste', { clipboardData: transfer }));
      else document.querySelector('.image-stage').dispatchEvent(new DragEvent('drop', { dataTransfer: transfer, bubbles: true }));
    }, { mode, bytes: [...png] });
    await expect(page.getByRole('button', { name: 'Biển 02' })).toBeVisible();
    expect(state.imageCalls).toBe(1);
  });
}

test('expired session redirects and failed session check can retry', async ({ page }) => {
  const state = await backend(page); await page.goto('/video');
  await expect(page.getByRole('button', { name: 'Chọn video', exact: true })).toBeVisible();
  state.authenticated = false; await page.reload();
  await expect(page).toHaveURL(/\/login/);
  state.authenticated = true;
  const unavailable = route => route.abort('failed');
  await page.route('**/api/auth/me', unavailable); await page.goto('/history');
  await expect(page.getByRole('heading', { name: 'Chưa kết nối được máy chủ' })).toBeVisible();
  await page.unroute('**/api/auth/me', unavailable);
  await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
  await expect(page.getByText('Trang 1 / 2', { exact: true })).toBeVisible();
});

test('video invalid extension, oversized file and failed job', async ({ page }) => {
  const state = await backend(page); await page.goto('/video');
  await page.getByLabel('Chọn video giao thông').setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('bad') });
  await expect(page.getByRole('alert').filter({ hasText: 'MP4, MOV, AVI hoặc WEBM' })).toBeVisible();
  const oversized = test.info().outputPath('oversized.mp4');
  const fd = fs.openSync(oversized, 'w');
  fs.ftruncateSync(fd, 100 * 1024 * 1024 + 1); fs.closeSync(fd);
  await page.getByLabel('Chọn video giao thông').setInputFiles(oversized);
  await expect(page.getByRole('alert').filter({ hasText: '100 MB' })).toBeVisible();
  expect(state.videoCalls).toBe(0);
  state.videoFailure = true;
  await page.getByLabel('Chọn video giao thông').setInputFiles(video);
  await expect(page.getByRole('alert').filter({ hasText: 'Không đọc được video thử nghiệm.' })).toBeVisible();
});

test('mobile navigation has no horizontal page overflow', async ({ page }) => {
  await backend(page); await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/', '/history', '/video']) {
    await page.goto(path); await expect(page.getByRole('button', { name: 'Đăng xuất', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});
