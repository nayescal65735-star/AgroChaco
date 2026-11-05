import { useState, useEffect, type ReactNode } from 'react';
import type { User, Role } from '../types';
import { DEMO_USERS } from '../services/mockData';
import { AuthContext } from './authContextDef';

const AUTH_STORAGE_KEY = 'agrochaco_auth_user';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored) as User;
      }
    } catch {
      // fallback
    }
    // Default demo user for easy entry
    return DEMO_USERS[0];
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, [user]);

  const loginAsDemo = (userId: string) => {
    const found = DEMO_USERS.find((u) => u.id === userId);
    if (found) {
      setUser(found);
    }
  };

  const loginCustom = (email: string, name?: string, role: Role = 'investigador') => {
    const newUser: User = {
      id: `custom-${Date.now()}`,
      name: name || email.split('@')[0],
      email,
      role,
      institution: 'Universidad Autónoma Gabriel René Moreno (UAGRM) - Chaco',
    };
    setUser(newUser);
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loginAsDemo,
        loginCustom,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
