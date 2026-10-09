// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

const ROWS = 8;
const COLS = 13;

const matrixEl = document.querySelector('#matrix');
const statusEl = document.querySelector('#status');

const cells = [];
for (let r = 0; r < ROWS; r++) {
  const row = [];
  for (let c = 0; c < COLS; c++) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    matrixEl.appendChild(cell);
    row.push(cell);
  }
  cells.push(row);
}

function setActive(row, col) {
  cells.forEach((r) => r.forEach((cell) => cell.classList.remove('active')));
  if (cells[row] && cells[row][col]) {
    cells[row][col].classList.add('active');
  }
}

const KEY_TO_DIR = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
};

const ui = new WebUI();

ui.on_connect(() => {
  statusEl.textContent = 'Connected — use the arrow keys';
});

ui.on_disconnect(() => {
  statusEl.textContent = 'Disconnected';
});

ui.on_message('position', (data) => {
  setActive(data.row, data.col);
});

window.addEventListener('keydown', (event) => {
  const dir = KEY_TO_DIR[event.key];
  if (!dir) return;
  event.preventDefault();
  ui.send_message('move', { dir });
});
