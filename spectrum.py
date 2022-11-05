import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from scipy.signal import find_peaks, peak_prominences
from scipy.stats import linregress
from scipy.optimize import curve_fit
from tools import normalize_minmax

class spectrum():
    '''
    Object to create and hold spectrum
    '''
    def __init__(self,
        filtered_waveforms,
        trap_heights=None,
        bins=2000,
        quantile=0.9905
        ):
        '''
        Initialize spectrum
        
        Parameters
        ----------
        filtered_waveforms: np.array
            array of filtered waveforms
        bins: int
            number of bins in spectrum
        quantile: float
            quantile of trapezoidal data which will be included in spectrum
            See self.make_calibration_spectrum for more info
        bin_max: float
            max bin range. if set to none, quantile is used
            Used for consisting plotting between spectra
        calibration: list
            [slope, y-intercept] of previous energy calibration
            must use same binning as calibration

        
        Returns
        --------
        spectrum: object
            histogrammed counts
        
        '''
        #TODO change input to raw waveforms and call trapezoidal filter from here
        self.bins = bins
        
        # find trapezoid heights if not provided
        if trap_heights is None:
            self.trapezoid_heights = find_trapezoid_heights(filtered_waveforms)
        else:
            self.trapezoid_heights = trap_heights
        
        self.make_calibration_spectrum(quantile=quantile)
        
    def add_additional_data(self,
        additional_waveforms):
        '''
        Add additional waveforms to spectrum
        
        Just used to find fwhm from pulser
        
        Paramters
        ---------
        additional_waveforms: ndarray
            array of additional waveforms to add
            
        '''
        new_trap_heights = find_trapezoid_heights(additional_waveforms)
        all_trap_heights = np.append(new_trap_heights,self.trapezoid_heights)
        
        self.counts_new, self.bin_edges_new = np.histogram(all_trap_heights, 
                bins=self.bins, 
                range=(self.bin_edges[0],self.bin_edges[1]))
        self.bin_centers_new = np.diff(self.bin_edges_new)
        self.channels_new = np.arange(len(self.bin_centers_new))
        
        
    def run_full_pipeline(self,
        energies,
        smoothed=False,
        prominence=100,
        width=[0,5],
        alternative='greater',
        E_res_window=7):
        '''
        Runs full pipeline of spectrum tools
        
        Finds gamma_peaks, energy calibration, and energy resolution.
        
        Parameters
        ----------
        energies: ndarray
            list of expected peak energies
        smoothed: bool
            whether to perform peak finding on smoothed spectrum
        prominence: float
            prominence for peak fitting
        
        
        Returns
        -------
        '''
        # find gamma ray peaks and prominences
        self.find_gamma_peaks(prominence=prominence,smoothed=smoothed,width=width)
        

        # ony perform energy calibration if more than one peak present
        if len(self.peaks) > 1:
            # find energy calibration
            self.find_energy_calibration(energies,alternative=alternative)
        
        # find FWHMs
        self.find_energy_resolution(E_window=E_res_window)
        
        # find Fano Factor
        #self.find_fano_factor()
        
        print('Done!')
        print('fwhms:',self.fwhms)
        
    def make_calibration_spectrum(self,
        quantile=0.9905):
        '''
        Make calibration spectrum
        
        Params
        ------
        quantile: float
            quantile of trapezoidal data which will be included in spectrum,
            which must be between 0 and 1 inclusive. Default value works for lab 1 data
            See np.quantile for more information
        bin_max: float
            max bin range. if set to none, quantile is used
            Used for consisting plotting between spectra
        
        Returns
        -------
        counts: ndarry
            counts in each histogrammed bin
        channels: ndarray
            bin_edges of histogram
        '''
        # Old implementation - felt a little too hacky
        # self.counts, self.channels = np.histogram(self.trapezoid_heights, 
        #     bins=self.bins, 
        #     range=(self.trapezoid_heights.min(),self.trapezoid_heights.min()*max_scaler))
        
        # make histogram of data from trapezoidal heights
        # cut max range to desired quantile of data
        # this is done to remove high end of spectrum from bad filtered pulses
        # quantile value can be changed to 1 if bad filtering is fixed
        self.counts, self.bin_edges = np.histogram(self.trapezoid_heights, 
            bins=self.bins, 
            range=(self.trapezoid_heights.min(),np.quantile(self.trapezoid_heights,quantile)))
        # else:
        #     self.counts, self.bin_edges = np.histogram(self.trapezoid_heights, 
        #         bins=self.bins, 
        #         range=(bin_limits))
        self.bin_centers = np.diff(self.bin_edges)
        # re-map channels to integers
        self.channels = np.arange(0,len(self.bin_centers))
        
    def smooth_spectrum(self,
        window_length=5,
        polyorder=1,
        show_plot=False,
        plot_savefile=None):
        '''
        Apply sagvol filter to smooth spectrum for peak fitting
        
        See scipy.signal.savgol_filter for more information
        
        Parameters
        ----------
        window_length: int
            Length of filter window
        polyorder: int
            Order of polynomial to fit samples
        show_plot: bool
            Whether to show plot of saved spectrum
        plot_savefile: str
            plot savefile name, not saved if left empty
        
        Returns
        -------
        
        '''
        print('Smoothing spectrum with Savgol filter')
        self.smoothed_counts = savgol_filter(self.counts, window_length, polyorder)
        if show_plot:
            plt.figure()
            plt.plot(self.channels, self.counts,label='Spectrum')
            plt.plot(self.channels, self.smoothed_counts,label='Savgol Smoothed Spectrum')
            plt.show()
            if plot_savefile is not None:
                plt.savefig(plot_savefile)
        
    def find_gamma_peaks(self,
        prominence=100,
        width=[0,5],
        smoothed=False,
        smoothed_window_length=5,
        show_plot=False,
        semilogy=False,
        plot_savefile=None):
        '''
        Find gamma-ray peaks
        
        See scipy.signal.find_peaks for more information
        
        Parameters 
        ----------
        prominence: float
            Required prominence of peaks
        smoothed: bool
            Whether to use smoothed version of spectrum for peak finding
        show_plot: bool
            Whether to show plot of saved spectrum
        plot_savefile: str
            plot savefile name, not saved if left empty
           
        Returns
        -------
        peaks: np.array
            Indices of peaks
        prominences: np.array
            Prominences for each peak in peaks
        
        '''
        # find peaks on smoothed spectrum
        if smoothed:
            self.smooth_spectrum(window_length=smoothed_window_length)
            print('Finding Peaks')
            self.peaks, self.prominences = find_peaks(self.smoothed_counts, prominence=prominence, width=width)
        
        # find peaks on raw spectrum
        else:
            print('Finding Peaks')
            self.peaks, self.prominences = find_peaks(self.counts, prominence = prominence, width = width)
        
        # show plot, if desired
        if show_plot:
            plt.figure()
            plt.plot(self.channels, self.counts,label='Spectrum Data')
            plt.plot(self.channels[self.peaks], self.counts[self.peaks], 'x', markersize = 5, label='Found Peaks')
            plt.xlabel('Channel Number')
            plt.ylabel('Counts')
            if semilogy:
                plt.semilogy()
            plt.legend()
            plt.show()
            if plot_savefile is not None:
                plt.savefig(plot_savefile)
                
    def find_energy_calibration(self,
        energies,
        alternative='two-sided'):
        '''
        Find linear energy calibration
        #TODO rearrange so the peak fitting tolerance changes based on desired energy
        
        Parameters
        ----------
        energies: ndarray
            array of expected gamma ray energies (keV)
        alternative : {'two-sided', 'less', 'greater'}, optional
            Defines the alternative hypothesis. Default is 'two-sided'.
            The following options are available:

            * 'two-sided': the slope of the regression line is nonzero
            * 'less': the slope of the regression line is less than zero
            * 'greater':  the slope of the regression line is greater than zero
            See scipy.stats.linregress for more infof
        
        Returns
        -------
        calibration_channels: ndarray
            array of channels associated with fitted peaks
        bin_energies: ndarray
            array of energies associated with calibration channels
        '''
        print('Finding energy calibration')
        # store energies to class
        self.energies = np.array(energies)
        
        # check that number of energies matches number of peaks
        assert len(self.peaks) == len(self.energies), "Number of peaks ("+str(len(self.peaks))+") and energies ("+str(len(self.energies))+") do not match. Change prominence."
        
        # grab calibration channels for peaks
        self.calibration_channels = self.channels[self.peaks]
        
        # perform linear regression
        result = linregress(self.calibration_channels,self.energies,alternative=alternative)
        
        # store relevant fit values
        self.slope = result.slope
        self.intercept = result.intercept
        self.pvalue = result.pvalue
        self.rvalue = result.rvalue
        self.stderr = result.stderr
        self.intercept_stderr = result.stderr
        #TODO actually use a linear fit instead of grade school fitting 
        # self.slope = (energies[-1] - energies[0]) / (self.calibration_channels[-1] - self.calibration_channels[0])
        # self.intercept = energies[0] - self.calibration_channels[0] * self.slope
        
        self.bin_energies = self.channels * self.slope + self.intercept
    
    def print_energy_calibration(self):
        '''
        Print lineaer energy calibration fit
        
        Returns
        -------
        energy_cal: str
            energy calibration equation
        '''
        string = 'Energy [keV] = '+str(round(self.slope,2))+' * Channel + '+str(round(self.intercept,2))
        print(string)
        return string
        
    def plot_spectrum(self,
        energy=True,
        show_calibrated_peaks=True,
        semilogy=False,
        plot_savefile=None):
        '''
        Plot Energy calibrated spectrum
        
        Parameters
        ----------
        energy: bool
            if true, plots x as energy, otherwise plots as channel number
        show_calibrated_peaks: bool
            whether to emphasized calibration peaks
        semilogy: bool
            whether to plot y on log axis
        plot_savefile: str
            plot savefile name, not saved if left empty
        
        Returns
        -------
        plot: matplotlib.pyplot.figure
            plot of spectrum with energy in keV on x-axis
        '''
        plt.figure()
        # Plot energy spectrum if desired
        if energy:
            plt.plot(self.bin_energies, self.counts)
            plt.xlabel('Energy (keV)')
        # Otherwise plot counts vs channels
        else:
            plt.plot(self.channels,self.counts)
            plt.xlabel('Channel')
        
        plt.ylabel('Counts')
        if show_calibrated_peaks:
            if energy:
                plt.plot(self.bin_energies[self.peaks], self.counts[self.peaks], 'x', markersize = 5)
            else:
                plt.plot(self.channels[self.peaks], self.counts[self.peaks], 'x', markersize = 5)
        if semilogy:
            plt.semilogy()
        plt.show()
        if plot_savefile is not None:
            plt.savefig(plot_savefile)
            
    def plot_energy_calibration(self,
        show_equation=False,
        plot_savefile=None):
        '''
        Plot energy calibration and linear fit
        
        Parameters
        ----------
        plot_savefile: str
            plot savefile name, not saved if left empty
        
        Return
        ------
        plot: matplotlib.pyplot.figure
            plot of Channel Energy in keV vs Channel
        '''
        plt.figure()
        plt.scatter(self.calibration_channels,self.energies,label='Calibration Peaks',c='tab:orange',s=10)
        plt.plot(self.channels,self.bin_energies,label='Linear Fit',c='tab:blue')
        plt.xlabel('Channel Number')
        plt.ylabel('Energy (keV)')
        if show_equation:
            plt.text(0,np.quantile(self.bin_energies,0.8),self.print_energy_calibration())
            plt.text(0,np.quantile(self.bin_energies,0.7),f'p_value = {self.pvalue:.3e}')
        plt.legend(loc='lower right')
        plt.show()
        if plot_savefile is not None:
            plt.savefig(plot_savefile)
    
    def find_fwhm(self,
        E_window=10,
        show_plot=False,
        show_fwhms=False,
        semilogy=False,
        plot_savefile=None):
        '''
        Find Energy resolution of peaks
        
        Parameters
        ----------
        E_window: float
            Energy window half_width in keV for gaus fitting
        show_plot: bool
            whether to show plot of fitted gaussians
        plot_savefile: str
            plot savefile name, not saved if left empty
        
        Returns
        -------
        fwhms: ndarray
            fwhm of fitted peaks in keV
        '''
        print('Finding energy resolution calibration')
        # initialize array to store fwhms
        self.fwhms = np.zeros(len(self.peaks))
        self.peak_counts = np.zeros(len(self.peaks))
        if show_plot:
            plt.figure()
        for i in range(len(self.peaks)):
            # grab centroid value
            centroid = self.peaks[i]
            # grab ROIs
            roi_x = self.bin_energies[centroid-E_window : centroid + E_window]
            roi_y = self.counts[centroid - E_window : centroid + E_window]
            # curve fit with scipy.optimize
            popt_gaussian, pcov_gaussian = curve_fit(gaussian,
                roi_x,
                roi_y,
                [self.counts[centroid],self.bin_energies[centroid],np.sqrt(self.counts[centroid])])
            # save fitted FWHM
            self.fwhms[i] = abs(popt_gaussian[2]*2.355)
            
            self.peak_counts[i] = roi_y.sum()
            # optinal plotting
            if show_plot:
                plt.plot(roi_x,roi_y)
                plt.plot(roi_x, gaussian(roi_x, *popt_gaussian), color='r',ls='--')
                if show_fwhms:
                    plt.text(roi_x.mean()-10,roi_y.max()+10,str(round(self.fwhms[i],2)))
        if show_plot:
            plt.xlabel('Energy (keV)')
            plt.ylabel('Counts')
            if semilogy:
                plt.semilogy()
            plt.show()
            if plot_savefile is not None:
                plt.savefig(plot_savefile)
                
    def find_energy_resolution(self):
        '''
        Find energy resolution
        
        Parameters
        ----------
        
        Returns
        -------
        '''
        self.find_fwhm()
        self.energy_resolution = self.fwhms / self.energies

        
    
    def plot_fwhms(self,
        plot_savefile=None):
        '''
        Plot energy resolution of fitted peaks
        
        Parameters
        ----------
        plot_savefile: str
            plot savefile name, not saved if left empty
        
        Returns
        -------
        plt: matplotlib.pyplot.figure
        
        '''
        plt.figure()
        plt.plot(self.energies,self.fwhms)
        plt.scatter(self.energies,self.fwhms)
        plt.title('FWHMs of Fitted Gamma-Ray Peaks')
        plt.ylabel('FWHM (keV)')
        plt.xlabel('Energy (keV)')
        plt.show()
        if plot_savefile is not None:
            plt.savefig(plot_savefile)
    
    def plot_energy_resolution(self,
        plot_savefile=None):
        '''
        Plot energy resolution of fitted peaks
        
        '''
        plt.figure()
        plt.plot(self.energies,self.energy_resolution*100)
        plt.scatter(self.energies,self.energy_resolution*100)
        plt.title('Energy Resolution')
        plt.ylabel('Energy Resolution (%)')
        plt.xlabel('Energy (keV)')
        plt.show()
        if plot_savefile is not None:
            plt.savefig(plot_savefile)
        
    
    def get_pulser_noise(self,
        pulser_trap_heights):
        '''
        Get FWHM of pulser'''
        return 0
            
    def find_fano_factor(self,
        W=2.96*10**-3,
        E_noise=3.2574542559794555):
        '''
        Find fano factor of peaks
        
        F = observed variance in N / Poisson predicted variance
        
        F can be found with the fitted energy resolution FWHM given the relation:
        FWHM = sqrt( E_statistic ** 2 + E_noise ** 2 )
        
        Where E_noise can be measured experimentally and E_statistic can be found through:
        E_statistic = 2.355 * sqrt(F * E_gamma * W)
        
        Rearranging these equations gives the relation to find the Fano factor:
        
        F = (FWHM ** 2 - E_noise ** 2) / (2.355 ** 2 * E_gamma * W)
        
        Parameters
        ----------
        W: float
            energy to generate electron hole pair in detector medium (in keV)
            2.96 eV used for Ge
        E_noise: float
            fwhm of noise as found from pulser. default is value i found 10/28
        
        Returns
        -------
        fano_factor: ndarray
            fano factor of peaks
        '''
        print('Finding Fano Factor')
        # E_noise=9.628062296356013

        self.fano_factor = (self.fwhms ** 2 - E_noise ** 2) / (2.355**2 * self.energies * W)
    
    def plot_fano_factor(self,
        display_mean_fano=False,
        plot_savefile=None):
        '''
        Plot fano factor vs energy
        
        Parameters
        ----------
        plot_savefile: str
            saves plot at var name if not empty
        
        
        Returns
        -------
        figure: matplotlib.pyplot.figure
        '''
        plt.figure()
        plt.plot(self.energies,self.fano_factor,marker='o')
        plt.xlabel('Energy (keV)')
        plt.ylabel('Fano Factor')
        if display_mean_fano:
            plt.text(np.quantile(self.energies,0.3),np.quantile(self.fano_factor,0.9),'Mean Fano Factor = '+str(round(self.fano_factor.mean(),2))+' +/- '+str(round(self.fano_factor.std(),2)))
        plt.show()
        if plot_savefile is not None:
            plt.savefig(plot_savefile)

        
            
    def find_efficiency_calibration(self,
        source_dist):
        '''
        Find efficency calibration
        
        Parameters
        ----------
        source_dist: float
            source-detector distance in meters
        Returns
        -------
        efficiency_calibration: ndarray
            efficency vs energy
        '''
        
        
        efficiency = intrinsic_efficiency * geometric_efficency
        
def find_trapezoid_heights(filtered_waveforms):
    '''
    Find trapezoid heights for all waveforms
    
    Parameters
    ----------
    filtered_waveforms: np.array
        array of filtered waveforms
        
    Returns
    -------
    trapezoidal_heights: np.array
        1D array of trapezoid height for each waveform
    '''
    return filtered_waveforms.max(axis=1)

def plot_trapezoid_height_histogram(trapezoid_heights,
        bins=8000,
        xlims=[0,1e17],
        semilogy=False,
        save_name=None):
    '''
    Plot trapezoid height histogram
    
    Parameters
    ----------
    trapezoid_heights: np.array
        height of trapezoid in filtered waveforms
    bins: int
        number of bins to use (default 8000)
    xlims: list
        min and max x in plot
    semilogy: bool
        whether to use semilog y or not
    save_name: str
        if not empty saves plot
    '''
    plt.figure()
    plt.hist(trapezoid_heights,bins=bins)
    plt.xlim(xlims)
    if semilogy:
        plt.semilogy()
    plt.show()
    if save_name is not None:
        plt.savefig(save_name)
    return

def gaussian(x, A, x0, sigma):
    '''
    Definition of gaussian for use in FWHM/peak fitting
    '''
    return A * np.exp(-(x - x0) ** 2 / (2 * sigma ** 2))
