"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light" | "system";

type Position =
  | "bottom-left"
  | "bottom-right"
  | "top-left"
  | "top-right";

type BubbleSize = "small" | "medium" | "large";

const STORAGE_KEYS = {
  theme: "sentinelscan-theme",
  position: "sentinelscan-bubble-position",
  size: "sentinelscan-bubble-size",
};

export default function Bubble() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>("dark");
  const [position, setPosition] =
    useState<Position>("bottom-right");
  const [size, setSize] =
    useState<BubbleSize>("medium");

  const [systemDark, setSystemDark] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem(
      STORAGE_KEYS.theme
    ) as Theme | null;

    const savedPosition = localStorage.getItem(
      STORAGE_KEYS.position
    ) as Position | null;

    const savedSize = localStorage.getItem(
      STORAGE_KEYS.size
    ) as BubbleSize | null;

    if (savedTheme) setTheme(savedTheme);
    if (savedPosition) setPosition(savedPosition);
    if (savedSize) setSize(savedSize);
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia(
      "(prefers-color-scheme: dark)"
    );

    const updateSystemTheme = () => {
      setSystemDark(mediaQuery.matches);
    };

    updateSystemTheme();

    mediaQuery.addEventListener(
      "change",
      updateSystemTheme
    );

    return () => {
      mediaQuery.removeEventListener(
        "change",
        updateSystemTheme
      );
    };
  }, []);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.theme,
      theme
    );
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.position,
      position
    );
  }, [position]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.size,
      size
    );
  }, [size]);

  const bubbleIsDark =
    theme === "dark" ||
    (theme === "system" && systemDark);

  const positionClasses: Record<
    Position,
    string
  > = {
    "bottom-left": "bottom-6 left-6",
    "bottom-right": "bottom-6 right-6",
    "top-left": "top-6 left-6",
    "top-right": "top-6 right-6",
  };

  /*
   * Size of the floating bubble.
   */
  const bubbleSizeClasses: Record<
    BubbleSize,
    string
  > = {
    small: "h-10 w-10 text-sm",
    medium: "h-12 w-12 text-base",
    large: "h-14 w-14 text-lg",
  };

  /*
   * Size of the complete Preferences GUI.
   *
   * This changes:
   * - panel width
   * - padding
   * - title
   * - labels
   * - select controls
   * - spacing
   */
  const panelSizeClasses: Record<
    BubbleSize,
    string
  > = {
    small: "w-60 p-3",
    medium: "w-72 p-4",
    large: "w-84 p-5",
  };

  const panelSpacingClasses: Record<
    BubbleSize,
    string
  > = {
    small: "space-y-3",
    medium: "space-y-4",
    large: "space-y-5",
  };

  const titleSizeClasses: Record<
    BubbleSize,
    string
  > = {
    small: "text-xs",
    medium: "text-sm",
    large: "text-base",
  };

  const descriptionSizeClasses: Record<
    BubbleSize,
    string
  > = {
    small: "text-[10px]",
    medium: "text-xs",
    large: "text-sm",
  };

  const labelSizeClasses: Record<
    BubbleSize,
    string
  > = {
    small: "text-[10px]",
    medium: "text-xs",
    large: "text-sm",
  };

  const selectSizeClasses: Record<
    BubbleSize,
    string
  > = {
    small: "px-2 py-1.5 text-xs",
    medium: "px-3 py-2 text-sm",
    large: "px-4 py-2.5 text-base",
  };

  /*
   * Keeps the Preferences menu attached
   * to the correct side of the bubble.
   */
  const menuPositionClasses: Record<
    Position,
    string
  > = {
    "bottom-left":
      "bottom-full left-0 mb-3",

    "bottom-right":
      "bottom-full right-0 mb-3",

    "top-left":
      "top-full left-0 mt-3",

    "top-right":
      "top-full right-0 mt-3",
  };

  const bubbleClasses = bubbleIsDark
    ? "border-zinc-600 bg-zinc-900 text-white hover:bg-zinc-800"
    : "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-100";

  const panelClasses = bubbleIsDark
    ? "border-zinc-700 bg-zinc-900 text-white"
    : "border-zinc-300 bg-white text-zinc-900";

  const labelClasses = bubbleIsDark
    ? "text-zinc-300"
    : "text-zinc-600";

  const secondaryTextClasses = bubbleIsDark
    ? "text-zinc-400"
    : "text-zinc-500";

  const selectClasses = bubbleIsDark
    ? "border-zinc-700 bg-zinc-800 text-white"
    : "border-zinc-300 bg-zinc-50 text-zinc-900";

  const closeButtonClasses = bubbleIsDark
    ? "text-zinc-400 hover:bg-zinc-800 hover:text-white"
    : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900";

  return (
    <div
      className={`fixed z-[9999] ${positionClasses[position]}`}
    >
      {open && (
        <div
          className={`absolute rounded-xl border shadow-2xl ${panelSizeClasses[size]} ${panelClasses} ${menuPositionClasses[position]}`}
        >
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2
                className={`font-semibold ${titleSizeClasses[size]}`}
              >
                Preferences
              </h2>

              <p
                className={`mt-1 ${secondaryTextClasses} ${descriptionSizeClasses[size]}`}
              >
                Bubble preferences
              </p>
            </div>

            <button
              type="button"
              onClick={() => setOpen(false)}
              className={`rounded-md px-2 py-1 ${closeButtonClasses}`}
              aria-label="Close preferences"
            >
              ×
            </button>
          </div>

          <div
            className={panelSpacingClasses[size]}
          >
            {/* Theme */}
            <div>
              <label
                className={`mb-2 block font-medium ${labelClasses} ${labelSizeClasses[size]}`}
              >
                Theme
              </label>

              <select
                value={theme}
                onChange={(event) =>
                  setTheme(
                    event.target.value as Theme
                  )
                }
                className={`w-full rounded-lg border outline-none focus:border-blue-500 ${selectClasses} ${selectSizeClasses[size]}`}
              >
                <option value="dark">
                  Dark
                </option>

                <option value="light">
                  Light
                </option>

                <option value="system">
                  System
                </option>
              </select>
            </div>

            {/* Position */}
            <div>
              <label
                className={`mb-2 block font-medium ${labelClasses} ${labelSizeClasses[size]}`}
              >
                Position
              </label>

              <select
                value={position}
                onChange={(event) =>
                  setPosition(
                    event.target.value as Position
                  )
                }
                className={`w-full rounded-lg border outline-none focus:border-blue-500 ${selectClasses} ${selectSizeClasses[size]}`}
              >
                <option value="bottom-left">
                  Bottom Left
                </option>

                <option value="bottom-right">
                  Bottom Right
                </option>

                <option value="top-left">
                  Top Left
                </option>

                <option value="top-right">
                  Top Right
                </option>
              </select>
            </div>

            {/* Size */}
            <div>
              <label
                className={`mb-2 block font-medium ${labelClasses} ${labelSizeClasses[size]}`}
              >
                Size
              </label>

              <select
                value={size}
                onChange={(event) =>
                  setSize(
                    event.target.value as BubbleSize
                  )
                }
                className={`w-full rounded-lg border outline-none focus:border-blue-500 ${selectClasses} ${selectSizeClasses[size]}`}
              >
                <option value="small">
                  Small
                </option>

                <option value="medium">
                  Medium
                </option>

                <option value="large">
                  Large
                </option>
              </select>
            </div>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() =>
          setOpen((current) => !current)
        }
        className={`${bubbleSizeClasses[size]} ${bubbleClasses} flex items-center justify-center rounded-full border font-semibold shadow-xl transition-all duration-200 hover:scale-105`}
        aria-label="Open preferences"
        aria-expanded={open}
      >
        ⚙
      </button>
    </div>
  );
}

