import { useState } from "react";
import { AssistantMenuI } from "./assistant_operations";

interface MenuItem {
  title: string;
  mcp: string;
  input: boolean;
  confirmation: boolean;
}

const AssistantMenu = ({ menu }: { menu: AssistantMenuI }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedItem, setSelectedItem] = useState<MenuItem | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [showConfirmation, setShowConfirmation] = useState(false);

  const menuItems = menu.getList() as MenuItem[];

  const handleItemClick = (item: MenuItem) => {
    setSelectedItem(item);
    if (item.input) {
      setInputValue("");
    } else if (item.confirmation) {
      setShowConfirmation(true);
    } else {
      executeAction(item);
    }
  };

  const executeAction = (item: MenuItem, input?: string) => {
    console.log("Executing:", item.title, input || "");
    // TODO: Implement actual action execution
    setSelectedItem(null);
    setShowConfirmation(false);
    setInputValue("");
  };

  const handleSubmit = () => {
    if (!selectedItem) return;

    if (selectedItem.confirmation) {
      setShowConfirmation(true);
    } else {
      executeAction(selectedItem, inputValue);
    }
  };

  const handleConfirm = () => {
    if (selectedItem) {
      executeAction(selectedItem, inputValue);
    }
  };

  return (
    <div className="fixed right-5 top-20 z-[1000]">
      {/* Menu Toggle Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-pink-500 text-white shadow-lg transition-all hover:scale-110 hover:shadow-xl"
        aria-label="Toggle menu"
      >
        <svg
          className={`h-6 w-6 transition-transform ${isExpanded ? "rotate-45" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 4v16m8-8H4"
          />
        </svg>
      </button>

      {/* Menu Panel */}
      {isExpanded && (
        <div className="mt-3 w-64 rounded-2xl bg-black/80 p-4 shadow-2xl backdrop-blur-md">
          <div className="space-y-2">
            {menuItems.map((item, index) => (
              <button
                key={index}
                onClick={() => handleItemClick(item)}
                className="w-full rounded-lg bg-white/10 px-4 py-3 text-left text-sm text-white transition hover:bg-white/20"
              >
                <div className="flex items-center justify-between">
                  <span>{item.title}</span>
                  {item.input && (
                    <svg
                      className="h-4 w-4 text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                      />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Modal */}
      {selectedItem?.input && !showConfirmation && (
        <div className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-96 rounded-2xl bg-gradient-to-br from-gray-900 to-gray-800 p-6 shadow-2xl">
            <h3 className="mb-4 text-lg font-semibold text-white">
              {selectedItem.title}
            </h3>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="Enter details..."
              className="mb-4 w-full rounded-lg border border-white/20 bg-white/10 px-4 py-3 text-white placeholder:text-gray-400 focus:border-white/40 focus:outline-none"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleSubmit}
                className="flex-1 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 px-4 py-2 text-white transition hover:opacity-90"
              >
                Continue
              </button>
              <button
                onClick={() => {
                  setSelectedItem(null);
                  setInputValue("");
                }}
                className="flex-1 rounded-lg bg-white/10 px-4 py-2 text-white transition hover:bg-white/20"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmation && selectedItem && (
        <div className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-96 rounded-2xl bg-gradient-to-br from-gray-900 to-gray-800 p-6 shadow-2xl">
            <h3 className="mb-2 text-lg font-semibold text-white">Confirm Action</h3>
            <p className="mb-4 text-gray-300">
              Are you sure you want to execute:{" "}
              <span className="font-semibold">{selectedItem.title}</span>
              {inputValue && (
                <span className="block mt-2 text-sm text-gray-400">
                  Input: {inputValue}
                </span>
              )}
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleConfirm}
                className="flex-1 rounded-lg bg-gradient-to-r from-green-500 to-emerald-500 px-4 py-2 text-white transition hover:opacity-90"
              >
                Confirm
              </button>
              <button
                onClick={() => {
                  setShowConfirmation(false);
                  setSelectedItem(null);
                  setInputValue("");
                }}
                className="flex-1 rounded-lg bg-white/10 px-4 py-2 text-white transition hover:bg-white/20"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AssistantMenu;
