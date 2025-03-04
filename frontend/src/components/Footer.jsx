import React from "react";

function Footer() {
  return (
    <footer className="bg-white">
      <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <div className="border-t border-gray-200 pt-4">
          <p className="text-center text-sm text-gray-500">
            &copy; {new Date().getFullYear()} Trading Bot Dashboard. All rights
            reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
