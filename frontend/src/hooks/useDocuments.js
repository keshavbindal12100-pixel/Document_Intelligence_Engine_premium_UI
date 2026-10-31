import { useCallback, useEffect, useState } from 'react';
import { apiRequest, normalizeDocument } from '../api/client.js';

export function useDocuments() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/api/v1/documents?page=1&page_size=100&sort_by=created_at&sort_order=desc');
      setDocuments((data?.items || []).map(normalizeDocument));
    } catch (err) {
      setError(err.message);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const removeDocument = useCallback(async (id) => {
    await apiRequest(`/api/v1/documents/${id}`, { method: 'DELETE' });
    await reload();
  }, [reload]);

  return { documents, loading, error, reload, removeDocument };
}
