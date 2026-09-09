function result = runScenario(config)
%RUNSCENARIO Run a fresh CSR simulation with explicit reproducible settings.
if nargin == 0, config = csr.scenario.smallNetwork(); end
if isfield(config,'Stack') && strcmp(config.Stack,'network')
    simulation = csr.sim.NetworkSimulation(config);
elseif isfield(config,'Stack') && strcmp(config.Stack,'mac-hop')
    simulation = csr.sim.MacHopSimulation(config);
else
    simulation = csr.Simulation(config);
end
result = simulation.run();
end
