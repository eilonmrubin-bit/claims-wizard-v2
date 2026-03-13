/**
 * Auto-save hook for case management.
 *
 * Features:
 * - Debounced auto-save (3 seconds after last change)
 * - Manual save with Ctrl+S
 * - Unsaved changes indicator
 * - beforeunload warning
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { SSOTInput } from '../types';

export type SaveStatus = 'saved' | 'saving' | 'unsaved' | 'error';

interface SaveResult {
  success: boolean;
  saved_at?: string;
  error?: string;
}

interface LoadResult {
  success: boolean;
  input?: SSOTInput;
  cache?: {
    input_hash: string;
    computed_at: string;
    ssot: Record<string, unknown>;
  };
  needs_recalculation: boolean;
  error?: string;
  version_warning?: string;
}

interface UseAutoSaveOptions {
  debounceMs?: number;
  enabled?: boolean;
}

interface UseAutoSaveReturn {
  caseId: string | null;
  setCaseId: (id: string | null) => void;
  saveStatus: SaveStatus;
  lastSavedAt: string | null;
  hasUnsavedChanges: boolean;
  save: (input: SSOTInput, cache?: Record<string, unknown>) => Promise<SaveResult>;
  load: (caseId: string) => Promise<LoadResult>;
  createNewCase: () => string;
  markDirty: () => void;
}

const generateCaseId = (): string => {
  return crypto.randomUUID ? crypto.randomUUID() :
    `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

export function useAutoSave(
  formData: SSOTInput,
  options: UseAutoSaveOptions = {}
): UseAutoSaveReturn {
  const { debounceMs = 3000, enabled = true } = options;

  const [caseId, setCaseId] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved');
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const formDataRef = useRef<SSOTInput>(formData);
  const cacheRef = useRef<Record<string, unknown> | null>(null);

  // Keep formDataRef updated
  useEffect(() => {
    formDataRef.current = formData;
  }, [formData]);

  // Save function
  const save = useCallback(async (
    input: SSOTInput,
    cache?: Record<string, unknown>
  ): Promise<SaveResult> => {
    if (!caseId) {
      return { success: false, error: 'No case ID set' };
    }

    setSaveStatus('saving');

    try {
      const response = await fetch('/cases/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          input,
          cache: cache || cacheRef.current,
        }),
      });

      const result = await response.json();

      if (result.success) {
        setSaveStatus('saved');
        setLastSavedAt(result.saved_at);
        setHasUnsavedChanges(false);
        if (cache) {
          cacheRef.current = cache;
        }
        return { success: true, saved_at: result.saved_at };
      } else {
        setSaveStatus('error');
        return { success: false, error: result.error };
      }
    } catch (err) {
      setSaveStatus('error');
      return { success: false, error: String(err) };
    }
  }, [caseId]);

  // Load function
  const load = useCallback(async (loadCaseId: string): Promise<LoadResult> => {
    try {
      const response = await fetch('/cases/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: loadCaseId }),
      });

      const result = await response.json();

      if (result.success) {
        setCaseId(loadCaseId);
        setSaveStatus('saved');
        setLastSavedAt(new Date().toISOString());
        setHasUnsavedChanges(false);
        if (result.cache) {
          cacheRef.current = result.cache;
        }
        return result;
      } else {
        return result;
      }
    } catch (err) {
      return { success: false, needs_recalculation: true, error: String(err) };
    }
  }, []);

  // Create new case
  const createNewCase = useCallback((): string => {
    const newId = generateCaseId();
    setCaseId(newId);
    setSaveStatus('unsaved');
    setHasUnsavedChanges(true);
    setLastSavedAt(null);
    cacheRef.current = null;
    return newId;
  }, []);

  // Mark as dirty (called when form changes)
  const markDirty = useCallback(() => {
    if (!hasUnsavedChanges) {
      setHasUnsavedChanges(true);
      setSaveStatus('unsaved');
    }
  }, [hasUnsavedChanges]);

  // Auto-save effect with debouncing
  useEffect(() => {
    if (!enabled || !caseId || !hasUnsavedChanges) {
      return;
    }

    // Clear previous timeout
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // Set new timeout
    debounceRef.current = setTimeout(() => {
      save(formDataRef.current);
    }, debounceMs);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [enabled, caseId, hasUnsavedChanges, debounceMs, save, formData]);

  // Keyboard shortcut (Ctrl+S)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (caseId && hasUnsavedChanges) {
          save(formDataRef.current);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [caseId, hasUnsavedChanges, save]);

  // beforeunload warning
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Update document title with unsaved indicator
  useEffect(() => {
    const caseName = formData.case_metadata?.case_name || 'תיק חדש';
    document.title = hasUnsavedChanges ? `* ${caseName} - אשף התביעות` : `${caseName} - אשף התביעות`;
  }, [hasUnsavedChanges, formData.case_metadata?.case_name]);

  return {
    caseId,
    setCaseId,
    saveStatus,
    lastSavedAt,
    hasUnsavedChanges,
    save,
    load,
    createNewCase,
    markDirty,
  };
}
