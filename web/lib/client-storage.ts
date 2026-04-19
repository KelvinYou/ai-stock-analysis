const MY_LIST_KEY = "desk.myList.v1";
const RECENT_KEY = "desk.recent.v1";
const RECENT_MAX = 5;

function safeRead<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function getMyList(): string[] {
  return safeRead<string[]>(MY_LIST_KEY, []);
}

export function toggleMyList(symbol: string): string[] {
  const list = getMyList();
  const next = list.includes(symbol) ? list.filter((s) => s !== symbol) : [...list, symbol];
  localStorage.setItem(MY_LIST_KEY, JSON.stringify(next));
  return next;
}

export function isStarred(symbol: string): boolean {
  return getMyList().includes(symbol);
}

export function getRecentlyViewed(): string[] {
  return safeRead<string[]>(RECENT_KEY, []);
}

export function addRecentlyViewed(symbol: string): void {
  const list = getRecentlyViewed().filter((s) => s !== symbol);
  const next = [symbol, ...list].slice(0, RECENT_MAX);
  localStorage.setItem(RECENT_KEY, JSON.stringify(next));
}
