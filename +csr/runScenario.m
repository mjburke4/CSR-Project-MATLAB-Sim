function result = runScenario(config)
%RUNSCENARIO Run a fresh CSR simulation with explicit reproducible settings.
if nargin == 0, config = csr.scenario.smallNetwork(); end
simulation = csr.Simulation(config);
result = simulation.run();
end
