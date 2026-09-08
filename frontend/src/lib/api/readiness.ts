const READY_TIMEOUT_MS = 150_000;
const READY_REQUEST_TIMEOUT_MS = 90_000;

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

let readinessPromise: Promise<void> | null = null;

async function pollUntilReady(onWaiting?: () => void): Promise<void> {
  const deadline = Date.now() + READY_TIMEOUT_MS;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`/api/ready?t=${Date.now()}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(
          Math.min(READY_REQUEST_TIMEOUT_MS, Math.max(1_000, deadline - Date.now()))
        ),
      });
      const body = (await response.json().catch(() => null)) as {
        ready?: boolean;
        retryAfterSeconds?: number;
      } | null;
      if (body?.ready === true) return;

      onWaiting?.();
      const retryDelay = Math.max(2_000, (body?.retryAfterSeconds ?? 5) * 1_000);
      await wait(Math.min(retryDelay, Math.max(0, deadline - Date.now())));
      continue;
    } catch {
      // A free Render instance can close the first request while waking.
    }

    onWaiting?.();
    await wait(Math.min(5_000, Math.max(0, deadline - Date.now())));
  }

  throw new Error("Services not ready");
}

/**
 * Wake the free backend once and share that operation between every caller in
 * the current browser tab (login, AuthGuard and concurrent API recovery).
 */
export function waitForBackendReady(onWaiting?: () => void): Promise<void> {
  if (!readinessPromise) {
    readinessPromise = pollUntilReady(onWaiting).finally(() => {
      readinessPromise = null;
    });
  }
  return readinessPromise;
}
