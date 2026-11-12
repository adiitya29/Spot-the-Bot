import { create } from "zustand";
import { initialRoomState, roomReducer, type RoomEvent, type RoomState } from "./reducer";

interface RoomStore extends RoomState {
  dispatch: (event: RoomEvent) => void;
  reset: () => void;
}

export const useRoomStore = create<RoomStore>((set) => ({
  ...initialRoomState,
  dispatch: (event) => set((state) => roomReducer(state, event)),
  reset: () => set(initialRoomState),
}));
