classdef SlotSelection
    %SLOTSELECTION Explicit executable-backed historical get_slot families.
    % Source: ns-3 486d9e01 model/csr-mac-core.h, GetActiveNodesForSlotting,
    % GetOpnetSlotRange and PickTxSlot. Historical selection is opt-in;
    % equal numeric seeds do not promise the ns-3/Modeler RNG sequence.
    methods (Static)
        function names = profiles()
            names = {'current-fine-free-slot', ...
                'hist-2014-coarse-inclusive-no-avoid', ...
                'hist-2014-zero-based-rebuild-list', ...
                'hist-2015-fine-one-based-table-no-avoid', ...
                'hist-2014-next-tslot-modulo-probe'};
        end

        function profile = normalizeProfile(profile)
            if isstring(profile) && isscalar(profile), profile = char(profile); end
            if ~ischar(profile) || ~isrow(profile) || ...
                    ~any(strcmp(profile,csr.mac.SlotSelection.profiles()))
                error('csr:mac:SlotProfile','SlotProfile must name a supported get_slot profile.');
            end
        end

        function active = activeNodes(profile,local,reported)
            % adb97 (campus modulo probe) and 08c364 (operational inclusive)
            % pass local active_nodes. Other ns-3 profiles retain max(local,
            % reported). Neither input is the global scenario node count.
            if any(strcmp(profile,{'hist-2014-coarse-inclusive-no-avoid', ...
                    'hist-2014-next-tslot-modulo-probe'}))
                active = double(local);
            else
                active = max(double(local),double(reported));
            end
        end

        function range = slotRange(profile,active,reduction)
            if nargin < 3, reduction = 0; end
            if any(strcmp(profile,{'hist-2014-coarse-inclusive-no-avoid', ...
                    'hist-2014-zero-based-rebuild-list', ...
                    'hist-2014-next-tslot-modulo-probe'}))
                if active <= 4
                    range = 31;
                elseif active <= 8
                    range = 63;
                elseif active <= 12
                    range = 127;
                else
                    range = 255;
                end
                if reduction > 0 && range-reduction > 1
                    range = range-reduction;
                end
            else
                range = csr.mac.Layer.slotRange(active,reduction);
            end
        end

        function slot = historicalSlot(profile,range,counters,initialDraw)
            % Resolve a supplied integer draw independently of RNG. This is
            % the production historical selection path and allows endpoint,
            % wraparound and source-defect regression vectors without tuning
            % random streams or introducing controlled-slot overrides.
            profile = csr.mac.SlotSelection.normalizeProfile(profile);
            validateattributes(range,{'numeric'}, ...
                {'scalar','real','finite','integer','positive','<=',255});
            validateattributes(initialDraw,{'numeric'}, ...
                {'scalar','real','finite','integer','nonnegative'});
            range = double(range); slot = double(initialDraw);
            lower = 0; upper = range;
            switch profile
                case 'hist-2014-zero-based-rebuild-list'
                    upper = range-1;
                case 'hist-2015-fine-one-based-table-no-avoid'
                    lower = 1;
                case 'current-fine-free-slot'
                    error('csr:mac:HistoricalSlotProfile', ...
                        'historicalSlot needs an explicit historical profile.');
            end
            if slot < lower || slot > upper
                error('csr:mac:HistoricalSlotDraw', ...
                    'Initial draw is outside the selected historical support.');
            end
            if strcmp(profile,'hist-2015-fine-one-based-table-no-avoid')
                % dd3f38 get_slot@0x1ffdd dereferences table[j], j=1..R.
                % Its 255-entry table has no index 255. The pinned ns-3
                % profile aborts on that recovered executable defect.
                if slot >= 255
                    error('csr:mac:HistoricalTableIndex', ...
                        'Historical fine-table get_slot selected invalid table index 255.');
                end
                return
            end
            if ~strcmp(profile,'hist-2014-next-tslot-modulo-probe'), return; end
            % adb97 get_slot@0x1f27e compares current next_tslot directly.
            % R is selectable only as a free initial draw. R -> 1 and
            % R-1 -> 0 on collisions are intentional modulo-R endpoints.
            probes = 0;
            while any(counters(:)==slot)
                slot = mod(slot+1,range);
                probes = probes+1;
                if probes > range
                    error('csr:mac:HistoricalProbeExhausted', ...
                        'Historical next_tslot probe exhausted slots 0..R-1.');
                end
            end
        end
    end
end
