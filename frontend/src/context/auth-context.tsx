"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone_number?: string;
  is_active: boolean;
  is_platform_admin: boolean;
}

export interface HotelMembership {
  membership_id: string;
  hotel_id: string;
  hotel_name: string;
  hotel_slug: string;
  role: string;
  city: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  memberships: HotelMembership[];
  activeHotel: HotelMembership | null;
  isLoading: boolean;
  login: (token: string, user: User, memberships: HotelMembership[]) => void;
  logout: () => void;
  switchHotel: (hotelId: string) => void;
  refreshUserData: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [memberships, setMemberships] = useState<HotelMembership[]>([]);
  const [activeHotel, setActiveHotel] = useState<HotelMembership | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const savedToken = localStorage.getItem("hotelos_token");
    const savedUser = localStorage.getItem("hotelos_user");
    const savedMemberships = localStorage.getItem("hotelos_memberships");
    const savedActiveHotelId = localStorage.getItem("hotelos_active_hotel_id");

    if (savedToken && savedUser) {
      try {
        const parsedUser = JSON.parse(savedUser);
        const parsedMemberships: HotelMembership[] = savedMemberships ? JSON.parse(savedMemberships) : [];
        setToken(savedToken);
        setUser(parsedUser);
        setMemberships(parsedMemberships);

        let active = parsedMemberships.find((m) => m.hotel_id === savedActiveHotelId);
        if (!active && parsedMemberships.length > 0) {
          active = parsedMemberships[0];
          localStorage.setItem("hotelos_active_hotel_id", active.hotel_id);
        }
        setActiveHotel(active || null);
      } catch (e) {
        console.error("Failed to parse cached auth state", e);
      }
    }
    setIsLoading(false);
  }, []);

  const login = (newToken: string, newUser: User, newMemberships: HotelMembership[]) => {
    setToken(newToken);
    setUser(newUser);
    setMemberships(newMemberships);

    localStorage.setItem("hotelos_token", newToken);
    localStorage.setItem("hotelos_user", JSON.stringify(newUser));
    localStorage.setItem("hotelos_memberships", JSON.stringify(newMemberships));

    let active = newMemberships[0] || null;
    if (active) {
      localStorage.setItem("hotelos_active_hotel_id", active.hotel_id);
    }
    setActiveHotel(active);

    if (newMemberships.length === 0) {
      router.push("/onboard");
    } else {
      router.push("/overview");
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    setMemberships([]);
    setActiveHotel(null);
    localStorage.removeItem("hotelos_token");
    localStorage.removeItem("hotelos_user");
    localStorage.removeItem("hotelos_memberships");
    localStorage.removeItem("hotelos_active_hotel_id");
    router.push("/login");
  };

  const switchHotel = (hotelId: string) => {
    const found = memberships.find((m) => m.hotel_id === hotelId);
    if (found) {
      setActiveHotel(found);
      localStorage.setItem("hotelos_active_hotel_id", found.hotel_id);
      window.location.reload();
    }
  };

  const refreshUserData = async () => {
    try {
      const data = await apiFetch<{ user: User; memberships: HotelMembership[] }>("/auth/me");
      setUser(data.user);
      setMemberships(data.memberships);
      localStorage.setItem("hotelos_user", JSON.stringify(data.user));
      localStorage.setItem("hotelos_memberships", JSON.stringify(data.memberships));

      const activeHotelId = localStorage.getItem("hotelos_active_hotel_id");
      let active = data.memberships.find((m) => m.hotel_id === activeHotelId);
      if (!active && data.memberships.length > 0) {
        active = data.memberships[0];
        localStorage.setItem("hotelos_active_hotel_id", active.hotel_id);
      }
      setActiveHotel(active || null);
    } catch (e) {
      console.error("Failed to refresh user profile", e);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        memberships,
        activeHotel,
        isLoading,
        login,
        logout,
        switchHotel,
        refreshUserData,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

