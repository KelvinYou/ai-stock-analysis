const MY_LIST_KEY = "desk.myList.v1";

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
