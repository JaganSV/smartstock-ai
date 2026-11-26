import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import MenuOpenIcon from '@mui/icons-material/MenuOpen';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import ListSubheader from '@mui/material/ListSubheader';
import Toolbar from '@mui/material/Toolbar';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { Fragment, useState } from 'react';
import { NavLink, Outlet } from 'react-router';

import { useAuth } from '../auth/AuthContext';
import HealthIndicator from './HealthIndicator';
import { visibleNavItems, type NavItem } from './navConfig';

export const DRAWER_WIDTH = 232;
export const DRAWER_COLLAPSED_WIDTH = 64;

/** "INVENTORY_MANAGER" -> "Inventory manager": display text only, never used for a decision. */
export function roleLabel(role: string): string {
  const words = role.toLowerCase().split('_').filter(Boolean).join(' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function groupBySection(items: NavItem[]): [string | undefined, NavItem[]][] {
  const groups: [string | undefined, NavItem[]][] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last[0] === item.section) last[1].push(item);
    else groups.push([item.section, [item]]);
  }
  return groups;
}

/** App bar, role-aware left navigation and the routed page. */
export default function AppShell() {
  const { session, logout, can } = useAuth();
  const [open, setOpen] = useState(true);
  const width = open ? DRAWER_WIDTH : DRAWER_COLLAPSED_WIDTH;
  const groups = groupBySection(visibleNavItems(can));

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap: 1 }}>
          <IconButton
            color="inherit"
            edge="start"
            aria-label={open ? 'Collapse navigation' : 'Expand navigation'}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <MenuOpenIcon /> : <MenuIcon />}
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }} noWrap>
            SmartStock AI
          </Typography>
          {session ? (
            <Box sx={{ textAlign: 'right', lineHeight: 1.2, minWidth: 0 }}>
              <Typography variant="body2" component="div" noWrap data-testid="user-name">
                {session.user.username}
              </Typography>
              <Typography variant="caption" component="div" noWrap data-testid="user-role">
                {roleLabel(session.user.role)}
              </Typography>
            </Box>
          ) : null}
          <Button color="inherit" startIcon={<LogoutIcon />} onClick={() => logout()}>
            Log out
          </Button>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width,
            boxSizing: 'border-box',
            overflowX: 'hidden',
            transition: 'width 150ms',
          },
        }}
      >
        <Toolbar />
        <Box component="nav" aria-label="Main navigation" sx={{ flexGrow: 1 }}>
          <List>
            {groups.map(([section, items]) => (
              <Fragment key={section ?? 'main'}>
                {section && open ? <ListSubheader disableSticky>{section}</ListSubheader> : null}
                {section && !open ? <Divider sx={{ my: 1 }} /> : null}
                {items.map((item) => {
                  const Icon = item.icon;
                  const label = section ? `${section} › ${item.label}` : item.label;
                  return (
                    <Tooltip key={item.path} title={open ? '' : label} placement="right">
                      <ListItemButton
                        component={NavLink}
                        to={item.path}
                        end={item.path === '/risk'}
                        aria-label={label}
                        sx={{ '&.active': { bgcolor: 'action.selected', fontWeight: 600 } }}
                      >
                        <ListItemIcon sx={{ minWidth: 40 }}>
                          <Icon />
                        </ListItemIcon>
                        {open ? <ListItemText primary={item.label} /> : null}
                      </ListItemButton>
                    </Tooltip>
                  );
                })}
              </Fragment>
            ))}
          </List>
        </Box>
        {open ? (
          <Box sx={{ p: 2 }}>
            <HealthIndicator />
          </Box>
        ) : null}
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, p: 3 }}>
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
