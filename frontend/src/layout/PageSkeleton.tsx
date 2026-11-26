import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';

/** Fallback while a lazily loaded page's code arrives (route-level code splitting). */
export default function PageSkeleton() {
  return (
    <Box aria-busy="true" aria-label="Loading page" sx={{ display: 'grid', gap: 2 }}>
      <Skeleton variant="text" width={280} sx={{ fontSize: '1.75rem' }} />
      <Skeleton variant="rounded" height={120} />
      <Skeleton variant="rounded" height={320} />
    </Box>
  );
}
