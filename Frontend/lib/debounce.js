/**
 * Simple debounce utility.
 *
 * Returns a wrapped function that delays invoking `fn` until `wait` ms have
 * elapsed since the last call. Useful for auto-save so we don't fire an API
 * request on every keystroke/click.
 *
 * The returned function also exposes `.cancel()` to clear a pending call.
 */
export function debounce(fn, wait = 1500) {
  let timeoutId = null;

  function debounced(...args) {
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      timeoutId = null;
      fn(...args);
    }, wait);
  }

  debounced.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  return debounced;
}
