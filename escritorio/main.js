const path = require("path");
const { app, BrowserWindow, globalShortcut, Menu } = require("electron");

const WIDGET = path.join(__dirname, "..", "widget", "index.html");

let win;

function crearVentana() {
  win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 900,
    minHeight: 600,
    show: false,
    backgroundColor: "#0b1120",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#0d1424",
      symbolColor: "#e6edf9",
      height: 36,
    },
  });

  win.loadFile(WIDGET);
  win.maximize();
  win.once("ready-to-show", () => win.show());
}

// Si ya hay una instancia abierta, esta se cierra y le devuelve el foco a la otra
const unica = app.requestSingleInstanceLock();

if (!unica) {
  app.quit();
} else {

  app.on("second-instance", () => {
    if (!win) return;
    if (win.isMinimized()) win.restore();
    if (!win.isVisible()) win.show();
    win.focus();
  });

  app.whenReady().then(() => {
    Menu.setApplicationMenu(null);
    crearVentana();

    globalShortcut.register("Alt+C", () => {
      win.isVisible() ? win.hide() : win.show();
    });
  });

  app.on("window-all-closed", () => app.quit());
  app.on("will-quit", () => globalShortcut.unregisterAll());
}