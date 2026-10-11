import { act } from "@testing-library/react";

// The upload goes through XMLHttpRequest (upload.onprogress, SPEC §6.4): tests install this fake
// to see the request and to report transfer progress by hand.
export class FakeXhr extends EventTarget {
  static instances: FakeXhr[] = [];

  readonly upload = new EventTarget();
  readonly headers: Record<string, string> = {};
  method = "";
  url = "";
  body: unknown = null;
  withCredentials = false;
  readyState = 0;
  status = 0;
  responseText = "";

  constructor() {
    super();
    FakeXhr.instances.push(this);
  }

  static get last(): FakeXhr {
    const xhr = FakeXhr.instances.at(-1);
    if (!xhr) throw new Error("no XMLHttpRequest was created");
    return xhr;
  }

  open(method: string, url: string | URL): void {
    this.method = method;
    this.url = String(url);
    this.readyState = 1;
  }

  setRequestHeader(name: string, value: string): void {
    this.headers[name] = value;
  }

  send(body: unknown): void {
    this.body = body;
  }

  abort(): void {
    this.dispatchEvent(new Event("abort"));
  }

  progress(loaded: number, total: number): void {
    act(() => {
      this.upload.dispatchEvent(
        new ProgressEvent("progress", { lengthComputable: true, loaded, total }),
      );
    });
  }

  respond(status: number, body: unknown): void {
    act(() => {
      this.status = status;
      this.responseText = JSON.stringify(body);
      this.readyState = 4;
      this.dispatchEvent(new ProgressEvent("load"));
      this.dispatchEvent(new ProgressEvent("loadend"));
    });
  }
}

export function installFakeXhr(): void {
  FakeXhr.instances = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
}
