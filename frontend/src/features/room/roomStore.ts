import { create } from "zustand";
import { initialRoomState, roomReducer } from "./reducer";
import type { RoomAction, RoomState } from "./types";

interface RoomStore extends RoomState {
  dispatch: (action: RoomAction) => void;
  reset: () => void;
}

export const useRoomStore = create<RoomStore>((set) => ({
  ...initialRoomState,
  dispatch: (action) => set((state) => roomReducer(state, action)),
  reset: () => set(initialRoomState),
}));
