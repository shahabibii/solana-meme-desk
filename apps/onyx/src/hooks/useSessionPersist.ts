import { useEffect } from "react";
import { buildSessionSnapshot, saveSession } from "../persist";
import { useDesk } from "../store";

/** Debounced sessionStorage sync — keeps feed/trades/equity across refresh. */
export function useSessionPersist() {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const unsub = useDesk.subscribe((state) => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        saveSession(buildSessionSnapshot(state));
      }, 400);
    });
    return () => {
      if (timer) clearTimeout(timer);
      unsub();
    };
  }, []);
}
