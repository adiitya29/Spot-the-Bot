import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getSoundEnabled,
  playCorrect,
  playRevealBot,
  playSuspense,
  playTick,
  playWrong,
  setSoundEnabled,
  toggleSound,
} from "../sound";

describe("Web Audio API sound module", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();

    // Mock AudioContext for jsdom
    const mockOscillator = {
      type: "sine",
      frequency: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
        linearRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
    };

    const mockGain = {
      gain: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
        linearRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
    };

    const mockContext = {
      state: "running",
      currentTime: 0,
      destination: {},
      createOscillator: vi.fn(() => mockOscillator),
      createGain: vi.fn(() => mockGain),
      resume: vi.fn().mockResolvedValue(undefined),
    };

    window.AudioContext = vi.fn().mockImplementation(() => mockContext);
  });

  it("defaults sound to enabled when localStorage is empty", () => {
    expect(getSoundEnabled()).toBe(true);
  });

  it("toggles sound and dispatches stb_sound_changed event", () => {
    const listener = vi.fn();
    window.addEventListener("stb_sound_changed", listener);

    const newState = toggleSound();
    expect(newState).toBe(false);
    expect(getSoundEnabled()).toBe(false);
    expect(listener).toHaveBeenCalled();

    const secondState = toggleSound();
    expect(secondState).toBe(true);
    expect(getSoundEnabled()).toBe(true);

    window.removeEventListener("stb_sound_changed", listener);
  });

  it("safely executes sound synthesis functions when enabled", () => {
    setSoundEnabled(true);

    expect(() => playTick()).not.toThrow();
    expect(() => playSuspense()).not.toThrow();
    expect(() => playRevealBot()).not.toThrow();
    expect(() => playCorrect()).not.toThrow();
    expect(() => playWrong()).not.toThrow();
  });

  it("bypasses audio synthesis when sound is disabled", () => {
    setSoundEnabled(false);

    expect(() => playTick()).not.toThrow();
    expect(() => playCorrect()).not.toThrow();
    expect(() => playWrong()).not.toThrow();
  });
});
