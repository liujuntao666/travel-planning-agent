export interface DebouncedFn<T extends (...args: never[]) => unknown> {
  (...args: Parameters<T>): void
  cancel: () => void
  flush: () => void
}

export function debounce<T extends (...args: never[]) => unknown>(
  fn: T,
  wait = 300,
): DebouncedFn<T> {
  let timer: ReturnType<typeof setTimeout> | null = null
  let lastArgs: Parameters<T> | null = null

  const invoke = () => {
    timer = null
    if (lastArgs) {
      const args = lastArgs
      lastArgs = null
      fn(...args)
    }
  }

  const debounced = ((...args: Parameters<T>) => {
    lastArgs = args
    if (timer) clearTimeout(timer)
    timer = setTimeout(invoke, wait)
  }) as DebouncedFn<T>

  debounced.cancel = () => {
    if (timer) clearTimeout(timer)
    timer = null
    lastArgs = null
  }

  debounced.flush = () => {
    if (timer) {
      clearTimeout(timer)
      invoke()
    }
  }

  return debounced
}
