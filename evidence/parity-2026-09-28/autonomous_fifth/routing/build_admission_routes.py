#!/usr/bin/env python3
"""Create an isolated Routes copy and record an exactly reversible edit.

The 99 issued model files are read only. Run from any working directory.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'autonomous_fourth/kit/autocase/model/+csr/+nwk/Routes.m'
TARGET = ROOT / 'autonomous_fifth/kit/autocase/+ac/AdmissionRoutes.m'
METHOD = '''        function admitNeighbor(obj,peer,linkCost,now)
            % ACK admission mirrors native TryMakeNeighborActive: a logical
            % destination is created, but a missing route candidate is not.
            % HELLO/measurement processing continues to use setNeighbor().
            obj.checkPeer(peer,linkCost,now);
            peer = double(peer); linkCost = double(linkCost);
            if isKey(obj.Peers,peer)
                entry = obj.Peers(peer);
                if entry.Active, return; end
            else
                entry = obj.emptyPeer(peer);
                entry.LinkCost = linkCost;
                obj.PeerOrder = [peer obj.PeerOrder];
            end
            % Native NoteDestinationCreated is unconditional at admission,
            % including when no observed direct candidate exists yet.
            obj.noteDestination(peer);
            before = obj.best(peer);
            entry.Active = true;
            obj.Peers(peer) = entry;
            % ReleaseDeferredRouteCandidates visits this destination only;
            % invalid entries and unrelated transit destinations stay intact.
            for k = 1:numel(obj.Candidates)
                route = obj.Candidates(k);
                if route.DestinationId == peer && route.Valid && ...
                        route.SelectionDeferred && obj.usable(route.NextHop)
                    obj.Candidates(k).SelectionDeferred = false;
                end
            end
            obj.finish(peer,before,false);
        end

'''

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    original = SOURCE.read_bytes()
    source = original.decode()
    assert source.count('classdef Routes < handle') == 1
    assert source.count('function obj = Routes(nodeId,capability,options)') == 1
    marker = '        function setNeighbor(obj,peer,active,linkCost,now)\n'
    assert source.count(marker) == 1
    modified = source.replace('classdef Routes < handle', 'classdef AdmissionRoutes < handle')
    modified = modified.replace('function obj = Routes(nodeId,capability,options)',
                                'function obj = AdmissionRoutes(nodeId,capability,options)')
    modified = modified.replace('csr.nwk.Routes', 'ac.AdmissionRoutes')
    modified = modified.replace(marker, METHOD + marker)
    # Private static helper references must refer to the isolated class too.
    assert 'csr.nwk.Routes' not in modified
    reverted = modified.replace(METHOD, '', 1)
    reverted = reverted.replace('ac.AdmissionRoutes', 'csr.nwk.Routes')
    reverted = reverted.replace('classdef AdmissionRoutes < handle', 'classdef Routes < handle')
    reverted = reverted.replace('function obj = AdmissionRoutes(nodeId,capability,options)',
                                'function obj = Routes(nodeId,capability,options)')
    assert reverted.encode() == original, 'Unexpected changes outside the admission method/class rename'
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(modified)
    assert SOURCE.read_bytes() == original
    receipt = {
        'source': str(SOURCE.relative_to(ROOT)),
        'target': str(TARGET.relative_to(ROOT)),
        'source_sha256': digest(original),
        'target_sha256': digest(modified.encode()),
        'source_bytes_unchanged': True,
        'reverse_transform_is_byte_identical': True,
        'class_reference_renames': source.count('csr.nwk.Routes'),
        'added_method': 'admitNeighbor(obj,peer,linkCost,now)',
        'scope': 'One new public method plus isolated class/constructor/self-reference renames',
        'native_source': 'autonomous/native_env/csr/model/csr-nwk-layer.h',
        'native_functions': ['TryMakeNeighborActive', 'NoteDestinationCreated',
                             'ReleaseDeferredRouteCandidates'],
        'matlab_runtime_executed': False,
    }
    (Path(__file__).parent / 'admission_routes_transform.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
