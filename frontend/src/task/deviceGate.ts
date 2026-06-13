/**
 * FR-44: block the experiment on touch-primary or undersized devices. Checked
 * once before `/sessions/{id}/start` is called.
 */
export function isDeviceBlocked(): boolean {
  const touchPrimary = navigator.maxTouchPoints > 0 && window.matchMedia("(pointer: coarse)").matches;
  const tooSmall = window.innerWidth < 1024 || window.innerHeight < 600;
  return touchPrimary || tooSmall;
}

export const DEVICE_BLOCKED_MESSAGE =
  "This experiment requires a desktop or laptop computer with a physical keyboard. Please switch devices and log in again.";
