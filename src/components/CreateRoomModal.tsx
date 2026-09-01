import React, { useState } from 'react';
import { Hash, X, Plus } from 'lucide-react';
import { createRoom } from '../services/api';
import { Room } from '../types';

interface CreateRoomModalProps {
  currentUser: { username: string };
  onClose: () => void;
  onRoomCreated: (room: Room) => void;
}

export const CreateRoomModal: React.FC<CreateRoomModalProps> = ({
  currentUser,
  onClose,
  onRoomCreated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setError(null);
    setLoading(true);
    try {
      const room = await createRoom(name.trim(), description.trim(), currentUser.username);
      onRoomCreated(room);
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
      else setError('Failed to create channel');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div
        id="create-room-modal-card"
        className="w-full max-w-md bg-[#111a2e] border border-slate-700/80 rounded-2xl shadow-2xl p-6"
      >
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-blue-600/20 text-blue-400">
              <Hash className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Create Channel</h2>
              <p className="text-xs text-slate-400">Create a new public discussion room</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-950/50 border border-red-500/40 text-red-200 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1" htmlFor="room-name-input">
              Channel Name
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-2.5 text-slate-500 text-sm">#</span>
              <input
                id="room-name-input"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                placeholder="e.g. general-tech, gaming, design"
                className="w-full pl-8 pr-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
              />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Lowercase letters, numbers, and dashes only</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1" htmlFor="room-desc-input">
              Description (Optional)
            </label>
            <input
              id="room-desc-input"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this channel about?"
              className="w-full px-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
            />
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex-1 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium rounded-xl transition-all shadow-md shadow-blue-600/20 flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>{loading ? 'Creating...' : 'Create Channel'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
