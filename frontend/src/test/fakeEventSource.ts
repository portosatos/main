import { act } from "@testing-library/react";

// jsdom has no EventSource: tests install this fake and drive the stream by hand.
export class FakeEventSource extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];

  readonly url: string;
  readonly withCredentials: boolean;
  readyState = FakeEventSource.CONNECTING;

  constructor(url: string | URL, init?: EventSourceInit) {
    super();
    this.url = String(url);
    this.withCredentials = init?.withCredentials ?? false;
    FakeEventSource.instances.push(this);
  }

  static get last(): FakeEventSource {
    const source = FakeEventSource.instances.at(-1);
    if (!source) throw new Error("no EventSource was created");
    return source;
  }

  close(): void {
    this.readyState = FakeEventSource.CLOSED;
  }

  // A server event: `event: <type>` and `data: <JSON>`.
  emit(type: string, data: unknown = {}): void {
    act(() => {
      this.readyState = FakeEventSource.OPEN;
      this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(data) }));
    });
  }

  // The connection broke; the browser reconnects by itself (CONNECTING) or gives up (CLOSED).
  fail(readyState: number = FakeEventSource.CONNECTING): void {
    act(() => {
      this.readyState = readyState;
      this.dispatchEvent(new Event("error"));
    });
  }
}

export function installFakeEventSource(): void {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
}
