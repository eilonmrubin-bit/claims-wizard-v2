/**
 * useUndoRedo - Undo/Redo hook for form state management.
 *
 * Features:
 * - Ctrl+Z = Undo, Ctrl+Shift+Z = Redo
 * - Debounced history entries (500ms)
 * - Maximum 50 entries in history
 * - Session-only (not persisted)
 */

import { useState, useEffect, useCallback, useRef } from 'react';

interface UseUndoRedoOptions {
  maxHistory?: number;
  debounceMs?: number;
}

interface UseUndoRedoReturn<T> {
  state: T;
  setState: (newState: T | ((prev: T) => T)) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  resetHistory: () => void;
}

export function useUndoRedo<T>(
  initialState: T,
  options: UseUndoRedoOptions = {}
): UseUndoRedoReturn<T> {
  const { maxHistory = 50, debounceMs = 500 } = options;

  // Current state
  const [state, setStateInternal] = useState<T>(initialState);

  // History stacks
  const [undoStack, setUndoStack] = useState<T[]>([]);
  const [redoStack, setRedoStack] = useState<T[]>([]);

  // Refs for debouncing
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStateRef = useRef<T | null>(null);
  const lastCommittedStateRef = useRef<T>(initialState);

  // Commit the current state to history
  const commitToHistory = useCallback((prevState: T, newState: T) => {
    // Don't add if state hasn't actually changed
    if (JSON.stringify(prevState) === JSON.stringify(newState)) {
      return;
    }

    setUndoStack((prev) => {
      const newStack = [...prev, prevState];
      // Keep only the last maxHistory entries
      if (newStack.length > maxHistory) {
        return newStack.slice(-maxHistory);
      }
      return newStack;
    });

    // Clear redo stack on new change
    setRedoStack([]);

    lastCommittedStateRef.current = newState;
  }, [maxHistory]);

  // Set state with debounced history
  const setState = useCallback((newStateOrUpdater: T | ((prev: T) => T)) => {
    setStateInternal((prevState) => {
      const newState = typeof newStateOrUpdater === 'function'
        ? (newStateOrUpdater as (prev: T) => T)(prevState)
        : newStateOrUpdater;

      // Clear existing debounce timer
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      // Store the state before this batch of changes
      if (pendingStateRef.current === null) {
        pendingStateRef.current = lastCommittedStateRef.current;
      }

      // Set up debounced commit
      debounceRef.current = setTimeout(() => {
        if (pendingStateRef.current !== null) {
          commitToHistory(pendingStateRef.current, newState);
          pendingStateRef.current = null;
        }
      }, debounceMs);

      return newState;
    });
  }, [commitToHistory, debounceMs]);

  // Undo
  const undo = useCallback(() => {
    if (undoStack.length === 0) return;

    // Commit any pending changes first
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }

    setUndoStack((prev) => {
      const newStack = [...prev];
      const prevState = newStack.pop();
      if (prevState === undefined) return prev;

      // Push current state to redo stack
      setRedoStack((redo) => [...redo, state]);

      // Restore previous state
      setStateInternal(prevState);
      lastCommittedStateRef.current = prevState;
      pendingStateRef.current = null;

      return newStack;
    });
  }, [undoStack, state]);

  // Redo
  const redo = useCallback(() => {
    if (redoStack.length === 0) return;

    setRedoStack((prev) => {
      const newStack = [...prev];
      const nextState = newStack.pop();
      if (nextState === undefined) return prev;

      // Push current state to undo stack
      setUndoStack((undo) => {
        const newUndo = [...undo, state];
        if (newUndo.length > maxHistory) {
          return newUndo.slice(-maxHistory);
        }
        return newUndo;
      });

      // Restore next state
      setStateInternal(nextState);
      lastCommittedStateRef.current = nextState;
      pendingStateRef.current = null;

      return newStack;
    });
  }, [redoStack, state, maxHistory]);

  // Reset history
  const resetHistory = useCallback(() => {
    setUndoStack([]);
    setRedoStack([]);
    lastCommittedStateRef.current = state;
    pendingStateRef.current = null;
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }, [state]);

  // Note: Ctrl+Z/Ctrl+Y keyboard shortcuts are handled in App.tsx

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  return {
    state,
    setState,
    undo,
    redo,
    canUndo: undoStack.length > 0,
    canRedo: redoStack.length > 0,
    resetHistory,
  };
}
