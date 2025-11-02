import React, { useState } from 'react';
import { Home, Download, List, Settings, History, Film, Tv, Plus, Play, Pause, Check, Clock, AlertCircle, ChevronDown, Search, RefreshCw, X, Trash2, Edit, Database, Bell, Calendar } from 'lucide-react';

const TubarrUI = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [showAddDownload, setShowAddDownload] = useState(false);
  const [downloadType, setDownloadType] = useState('tv');

  // Mock data matching your current structure
  const stats = {
    totalShows: 6,
    totalEpisodes: 38,
    totalMovies: 0,
    activeJobs: 0,
    storageUsed: '12.13 GB'
  };

  const recentJobs = [
    { show: 'Tech Quickie', season: '03', status: 'completed', created: '09/06/2025, 14:30:15' },
    { show: 'Game Theory', season: '02', status: 'completed', created: '09/06/2025, 12:15:42' },
    { show: 'Film Theory', season: '05', status: 'failed', created: '08/06/2025, 18:22:10' }
  ];

  const recentMedia = [
    { show: 'The third test', season: 'Season 01', episodes: 1, modified: '09/06/2025, 12:32:25' },
    { show: 'The second test', season: 'Season 01', episodes: 1, modified: '09/06/2025, 12:21:35' },
    { show: 'The Test', season: 'Season 01', episodes: 2, modified: '08/06/2025, 14:38:28' },
    { show: 'Off_the_Hook', season: 'Season 01', episodes: 9, modified: '08/06/2025, 01:28:44' },
    { show: 'Off the Hook', season: 'Season 01', episodes: 25, modified: '01/04/2025, 22:26:42' }
  ];

  const subscriptions = [
    { 
      id: 1, 
      name: 'Tech Quickie', 
      channel: '@TechQuickie',
      tracked: true, 
      episodes: 156, 
      lastCheck: '2 hours ago', 
      newVideos: 2,
      retention: 'Keep last 50',
      autoDownload: true
    },
    { 
      id: 2, 
      name: 'Game Theory', 
      channel: '@GameTheory',
      tracked: true, 
      episodes: 89, 
      lastCheck: '5 hours ago', 
      newVideos: 0,
      retention: 'Keep last 100',
      autoDownload: true
    },
    { 
      id: 3, 
      name: 'Off the Hook', 
      channel: '@OffTheHook',
      tracked: true, 
      episodes: 45, 
      lastCheck: '1 hour ago', 
      newVideos: 0,
      retention: 'Keep all',
      autoDownload: false
    }
  ];

  const TabButton = ({ icon: Icon, label, tabName }) => (
    <button
      onClick={() => setActiveTab(tabName)}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
        activeTab === tabName
          ? 'bg-blue-600 text-white shadow-lg'
          : 'text-gray-400 hover:bg-gray-800 hover:text-white'
      }`}
    >
      <Icon size={20} />
      <span className="font-medium">{label}</span>
    </button>
  );

  const StatCard = ({ label, value, icon: Icon, color }) => (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-gray-600 transition-all">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm mb-1 uppercase tracking-wide">{label}</p>
          <p className="text-3xl font-bold text-white">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon size={24} className="text-white" />
        </div>
      </div>
    </div>
  );

  const SubscriptionCard = ({ subscription }) => (
    <div className="bg-gray-800 rounded-lg p-5 border border-gray-700 hover:border-gray-600 transition-all">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-white font-semibold text-lg">{subscription.name}</h3>
            {subscription.newVideos > 0 && (
              <span className="bg-blue-600 text-white text-xs px-2 py-0.5 rounded-full font-medium">
                {subscription.newVideos} new
              </span>
            )}
          </div>
          <p className="text-gray-400 text-sm mb-2">{subscription.channel}</p>
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span>{subscription.episodes} episodes</span>
            <span>•</span>
            <span>Last check: {subscription.lastCheck}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="p-2 hover:bg-gray-700 rounded-lg transition-colors" title="Edit subscription">
            <Edit size={18} className="text-gray-400" />
          </button>
          <button className="p-2 hover:bg-gray-700 rounded-lg transition-colors" title="Delete subscription">
            <Trash2 size={18} className="text-gray-400" />
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-3 mb-4 p-3 bg-gray-900 rounded-lg">
        <div>
          <p className="text-gray-500 text-xs mb-1">Retention</p>
          <p className="text-gray-300 text-sm font-medium">{subscription.retention}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs mb-1">Auto Download</p>
          <p className="text-gray-300 text-sm font-medium">{subscription.autoDownload ? 'Enabled' : 'Disabled'}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs mb-1">Status</p>
          <p className="text-green-400 text-sm font-medium">Active</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button className="flex-1 flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg text-sm font-medium transition-colors">
          <RefreshCw size={16} />
          Check Now
        </button>
        <button className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg text-sm font-medium transition-colors">
          <Download size={16} />
          Download New
        </button>
      </div>
    </div>
  );

  const AddDownloadModal = () => (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-2xl p-6 max-w-2xl w-full border border-gray-700 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">New Download</h2>
          <button 
            onClick={() => setShowAddDownload(false)}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X size={24} className="text-gray-400" />
          </button>
        </div>

        <div className="flex gap-3 mb-6">
          <button
            onClick={() => setDownloadType('tv')}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg font-medium transition-all ${
              downloadType === 'tv'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            <Tv size={20} />
            TV Show / Playlist
          </button>
          <button
            onClick={() => setDownloadType('movie')}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg font-medium transition-all ${
              downloadType === 'movie'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            <Film size={20} />
            Movie / Single Video
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-gray-300 text-sm font-medium mb-2">
              YouTube URL
            </label>
            <input
              type="text"
              placeholder="https://youtube.com/playlist?list=..."
              className="w-full bg-gray-700 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-gray-300 text-sm font-medium mb-2">
              {downloadType === 'tv' ? 'Show Name' : 'Movie Name'}
            </label>
            <input
              type="text"
              placeholder={downloadType === 'tv' ? 'e.g., Tech Quickie' : 'e.g., Documentary Title'}
              className="w-full bg-gray-700 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {downloadType === 'tv' && (
            <>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-gray-300 text-sm font-medium mb-2">
                    Season Number
                  </label>
                  <input
                    type="number"
                    placeholder="01"
                    className="w-full bg-gray-700 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 text-sm font-medium mb-2">
                    Start Episode
                  </label>
                  <input
                    type="number"
                    placeholder="01"
                    className="w-full bg-gray-700 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-gray-300 text-sm font-medium mb-2">
                    Playlist Start
                  </label>
                  <input
                    type="number"
                    placeholder="1"
                    className="w-full bg-gray-700 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-3 p-4 bg-gray-900 rounded-lg">
                  <input
                    type="checkbox"
                    id="track-playlist"
                    defaultChecked
                    className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="track-playlist" className="text-gray-300 text-sm flex-1">
                    Track this playlist as a subscription
                  </label>
                </div>

                <div className="p-4 bg-gray-900 rounded-lg space-y-3">
                  <h4 className="text-gray-300 font-medium text-sm">Subscription Settings</h4>
                  
                  <div>
                    <label className="block text-gray-400 text-xs mb-2">Retention Policy</label>
                    <select className="w-full bg-gray-700 text-white px-3 py-2 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none text-sm">
                      <option>Keep all episodes</option>
                      <option>Keep last 10 episodes</option>
                      <option>Keep last 25 episodes</option>
                      <option>Keep last 50 episodes</option>
                      <option>Keep last 100 episodes</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      id="auto-download"
                      defaultChecked
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                    />
                    <label htmlFor="auto-download" className="text-gray-300 text-sm">
                      Automatically download new episodes
                    </label>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={() => setShowAddDownload(false)}
            className="flex-1 bg-gray-700 text-gray-300 py-3 rounded-lg font-medium hover:bg-gray-600 transition-colors"
          >
            Cancel
          </button>
          <button className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
            Start Download
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-br from-red-600 to-red-700 p-2.5 rounded-lg shadow-lg">
                <Play size={24} className="fill-white text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">TUBARR</h1>
                <p className="text-gray-400 text-sm">YouTube to Jellyfin Manager</p>
              </div>
            </div>
            <button
              onClick={() => setShowAddDownload(true)}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-colors shadow-lg"
            >
              <Plus size={20} />
              New Download
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex gap-6">
          {/* Sidebar */}
          <aside className="w-64 flex-shrink-0">
            <nav className="space-y-2 sticky top-24">
              <TabButton icon={Home} label="Dashboard" tabName="dashboard" />
              <TabButton icon={Plus} label="New TV Download" tabName="new-tv" />
              <TabButton icon={Film} label="New Movie Download" tabName="new-movie" />
              <TabButton icon={List} label="Jobs" tabName="jobs" />
              <TabButton icon={History} label="History" tabName="history" />
              <TabButton icon={Bell} label="Subscriptions" tabName="subscriptions" />
              <TabButton icon={Database} label="Media Library" tabName="media" />
              <TabButton icon={Settings} label="Settings" tabName="settings" />
            </nav>
          </aside>

          {/* Main Content */}
          <main className="flex-1">
            {activeTab === 'dashboard' && (
              <div className="space-y-6">
                <h2 className="text-3xl font-bold">Dashboard</h2>
                
                {/* Stats Grid */}
                <div className="grid grid-cols-5 gap-4">
                  <StatCard label="Total Shows" value={stats.totalShows} icon={Tv} color="bg-blue-600" />
                  <StatCard label="Total Episodes" value={stats.totalEpisodes} icon={Film} color="bg-green-600" />
                  <StatCard label="Total Movies" value={stats.totalMovies} icon={Film} color="bg-purple-600" />
                  <StatCard label="Active Jobs" value={stats.activeJobs} icon={RefreshCw} color="bg-cyan-600" />
                  <StatCard label="Storage Used" value={stats.storageUsed} icon={Database} color="bg-yellow-600" />
                </div>

                {/* Two Column Layout */}
                <div className="grid grid-cols-2 gap-6">
                  {/* Recent Jobs */}
                  <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-xl font-bold">Recent Jobs</h3>
                      <button 
                        onClick={() => setActiveTab('jobs')}
                        className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                      >
                        View All
                      </button>
                    </div>
                    
                    {recentJobs.length === 0 ? (
                      <div className="text-center py-8 text-gray-400">
                        No jobs found
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {recentJobs.map((job, idx) => (
                          <div key={idx} className="flex items-center justify-between p-3 bg-gray-900 rounded-lg hover:bg-gray-750 transition-colors">
                            <div className="flex-1">
                              <p className="text-white font-medium">{job.show}</p>
                              <p className="text-gray-400 text-sm">Season {job.season}</p>
                            </div>
                            <div className="text-right">
                              <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                                job.status === 'completed' ? 'bg-green-600/20 text-green-400' :
                                job.status === 'failed' ? 'bg-red-600/20 text-red-400' :
                                'bg-blue-600/20 text-blue-400'
                              }`}>
                                {job.status}
                              </span>
                              <p className="text-gray-500 text-xs mt-1">{job.created}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Recent Media */}
                  <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-xl font-bold">Recent Media</h3>
                      <button 
                        onClick={() => setActiveTab('media')}
                        className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                      >
                        View All
                      </button>
                    </div>
                    
                    <div className="space-y-3">
                      {recentMedia.map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-gray-900 rounded-lg hover:bg-gray-750 transition-colors">
                          <div className="flex-1">
                            <p className="text-white font-medium">{item.show}</p>
                            <p className="text-gray-400 text-sm">{item.season} • {item.episodes} episode{item.episodes > 1 ? 's' : ''}</p>
                          </div>
                          <p className="text-gray-500 text-xs">{item.modified}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'subscriptions' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-3xl font-bold">Subscriptions</h2>
                    <p className="text-gray-400 mt-1">Manage channel subscriptions with automated downloads and retention</p>
                  </div>
                  <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                    <RefreshCw size={16} />
                    Check All for Updates
                  </button>
                </div>
                <div className="grid gap-4">
                  {subscriptions.map(subscription => (
                    <SubscriptionCard key={subscription.id} subscription={subscription} />
                  ))}
                </div>
              </div>
            )}

            {(activeTab === 'new-tv' || activeTab === 'new-movie') && (
              <div className="max-w-2xl">
                <h2 className="text-3xl font-bold mb-6">
                  {activeTab === 'new-tv' ? 'New TV Download' : 'New Movie Download'}
                </h2>
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                  <AddDownloadModal />
                </div>
              </div>
            )}

            {activeTab === 'jobs' && (
              <div className="space-y-6">
                <h2 className="text-3xl font-bold">Jobs</h2>
                <div className="bg-gray-800 rounded-xl border border-gray-700">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-900 border-b border-gray-700">
                        <tr>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Show</th>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Season</th>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Status</th>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Created</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {recentJobs.length === 0 ? (
                          <tr>
                            <td colSpan="4" className="px-6 py-12 text-center text-gray-400">
                              No jobs found
                            </td>
                          </tr>
                        ) : (
                          recentJobs.map((job, idx) => (
                            <tr key={idx} className="hover:bg-gray-750 transition-colors">
                              <td className="px-6 py-4 text-white">{job.show}</td>
                              <td className="px-6 py-4 text-gray-300">{job.season}</td>
                              <td className="px-6 py-4">
                                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                                  job.status === 'completed' ? 'bg-green-600/20 text-green-400' :
                                  job.status === 'failed' ? 'bg-red-600/20 text-red-400' :
                                  'bg-blue-600/20 text-blue-400'
                                }`}>
                                  {job.status}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-gray-400">{job.created}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'media' && (
              <div className="space-y-6">
                <h2 className="text-3xl font-bold">Media Library</h2>
                <div className="bg-gray-800 rounded-xl border border-gray-700">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-900 border-b border-gray-700">
                        <tr>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Show</th>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Season</th>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Episodes</th>
                          <th className="text-left px-6 py-4 text-gray-400 font-medium">Modified</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {recentMedia.map((item, idx) => (
                          <tr key={idx} className="hover:bg-gray-750 transition-colors">
                            <td className="px-6 py-4 text-white">{item.show}</td>
                            <td className="px-6 py-4 text-gray-300">{item.season}</td>
                            <td className="px-6 py-4 text-gray-300">{item.episodes}</td>
                            <td className="px-6 py-4 text-gray-400">{item.modified}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="space-y-6">
                <h2 className="text-3xl font-bold">Settings</h2>
                <div className="bg-gray-800 rounded-xl border border-gray-700 divide-y divide-gray-700">
                  {[
                    { title: 'Video Quality', value: '1080p', desc: 'Maximum video resolution' },
                    { title: 'H.265 Conversion', value: 'Enabled', desc: 'Convert videos for better compression' },
                    { title: 'CRF Quality', value: '28', desc: 'Compression quality (lower = better, larger files)' },
                    { title: 'Concurrent Jobs', value: '1', desc: 'Number of simultaneous downloads' },
                    { title: 'Update Check Interval', value: '60 minutes', desc: 'How often to check subscriptions' },
                    { title: 'Completed Jobs Limit', value: '10', desc: 'Number of completed jobs to keep in history' },
                    { title: 'Jellyfin Integration', value: 'Disabled', desc: 'Direct copy to Jellyfin library' }
                  ].map((setting, idx) => (
                    <div key={idx} className="p-5 flex items-center justify-between hover:bg-gray-750 transition-colors">
                      <div>
                        <h3 className="text-white font-medium">{setting.title}</h3>
                        <p className="text-gray-400 text-sm mt-1">{setting.desc}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-blue-400 font-medium">{setting.value}</span>
                        <button className="p-2 hover:bg-gray-700 rounded-lg transition-colors">
                          <ChevronDown size={20} className="text-gray-400" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </main>
        </div>
      </div>

      {showAddDownload && <AddDownloadModal />}
    </div>
  );
};

export default TubarrUI;
