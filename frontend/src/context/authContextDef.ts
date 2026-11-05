import { createContext } from 'react';
import type { User, Role } from '../types';

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loginAsDemo: (userId: string) => void;
  loginCustom: (email: string, name?: string, role?: Role) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
