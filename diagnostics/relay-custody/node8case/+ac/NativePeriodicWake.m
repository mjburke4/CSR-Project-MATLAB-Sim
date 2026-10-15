classdef NativePeriodicWake
    % Local aligned, phase-zero native wake query for integer-ns IdleRTS.
    % This intentionally retains the reference's floating expiry boundary.
    % It does not change the scheduler or the actual periodic wake timer.
    methods (Static)
        function nextSeconds = next(nowNanoseconds,cycle,awakeWindow)
            nowSeconds = double(nowNanoseconds) / 1e9;
            if nowSeconds < cycle
                nextSeconds = cycle;
                return;
            end
            offset = ac.NativePeriodicWake.positiveFmod(nowSeconds,cycle);
            if offset < awakeWindow
                nextSeconds = nowSeconds;
            else
                nextSeconds = nowSeconds + cycle - offset;
            end
        end

        function remainder = positiveFmod(value,divisor)
            % MATLAB rem snaps some near-integer quotients to zero. Native
            % std::fmod retains their binary remainder. Power-of-two scaling
            % is exact; each taken subtraction has operands within factor2
            % and is exact (Sterbenz). No rounded quotient/product or epsilon.
            assert(isfinite(value) && value >= 0 && ...
                isfinite(divisor) && divisor > 0);
            remainder = value;
            if remainder < divisor, return; end
            scaled = divisor;
            while scaled <= remainder / 2
                scaled = scaled * 2;
            end
            while scaled >= divisor
                if remainder >= scaled, remainder = remainder - scaled; end
                scaled = scaled / 2;
            end
        end
    end
end
