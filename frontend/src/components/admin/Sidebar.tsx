'use client';

import Link from 'next/link';

const MENU_ITEMS = [
  { href: '/admin', label: 'Dashboard' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/personas', label: 'Personas' },
  { href: '/admin/content', label: 'Content' },
  { href: '/admin/policy', label: 'Policy' },
  { href: '/admin/models', label: 'LLM Models' },
  { href: '/admin/usage', label: 'Usage & Billing' },
  { href: '/admin/monitoring', label: 'Monitoring' },
];

export function Sidebar() {
  return (
    <aside className="admin-sidebar">
      <h2>Admin</h2>
      <nav>
        <ul>
          {MENU_ITEMS.map((item) => (
            <li key={item.href}>
              <Link href={item.href}>{item.label}</Link>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
